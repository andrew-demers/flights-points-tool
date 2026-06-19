#!/usr/bin/env bash
# install.sh - Set up flights-points-tool + Google Flights MCP for Claude Code
#
# Usage:
#   ./install.sh                        # installs everything, prompts for seats.aero key
#   SEATS_AERO_API_KEY=xxx ./install.sh # non-interactive if key already in env
#   ./install.sh --no-scrape            # skip Playwright browser scraper install

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FLIGHTS_POINTS_DIR="$(dirname "$SCRIPT_DIR")"
FLIGHTS_MCP_REPO="https://github.com/smamidipaka6/flights-mcp-server.git"
FLIGHTS_MCP_DEFAULT_DIR="$(dirname "$FLIGHTS_POINTS_DIR")/flights-mcp-server"
SKILL_NAME="find-flights-points"
SKILL_SRC="$FLIGHTS_POINTS_DIR/skill"
SKILL_DEST="$HOME/.claude/skills/$SKILL_NAME"

NO_SCRAPE=false
for arg in "$@"; do
  [[ "$arg" == "--no-scrape" ]] && NO_SCRAPE=true
done

# ── helpers ──────────────────────────────────────────────────────────────────

green()  { printf '\033[0;32m%s\033[0m\n' "$*"; }
yellow() { printf '\033[0;33m%s\033[0m\n' "$*"; }
red()    { printf '\033[0;31m%s\033[0m\n' "$*"; }
step()   { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }

require() {
  command -v "$1" &>/dev/null || { red "Error: '$1' is required but not found. $2"; exit 1; }
}

mcp_registered() {
  claude mcp list 2>/dev/null | grep -q "^$1:"
}

# ── prereqs ──────────────────────────────────────────────────────────────────

step "Checking prerequisites"
require uv  "Install from https://docs.astral.sh/uv/getting-started/installation/"
require claude "Install Claude Code CLI from https://claude.ai/code"
green "  uv and claude found"

# ── seats.aero API key ───────────────────────────────────────────────────────

step "seats.aero API key"
if [[ -z "${SEATS_AERO_API_KEY:-}" ]]; then
  echo "  seats.aero gives real award availability for American, United, and Delta"
  echo "  (Pro account required - https://seats.aero)"
  read -rp "  Enter your seats.aero API key (or press Enter to skip): " SEATS_AERO_API_KEY
fi
if [[ -n "$SEATS_AERO_API_KEY" ]]; then
  green "  API key set"
else
  yellow "  Skipped - will fall back to browser scrapers when available"
fi

# ── flights-mcp-server ───────────────────────────────────────────────────────

step "Google Flights MCP server"
if mcp_registered "flights"; then
  green "  Already registered as 'flights' MCP - skipping"
else
  # Find or clone the repo
  if [[ -d "$FLIGHTS_MCP_DEFAULT_DIR" ]]; then
    FLIGHTS_MCP_DIR="$FLIGHTS_MCP_DEFAULT_DIR"
    green "  Found at $FLIGHTS_MCP_DIR"
  else
    echo "  Not found at $FLIGHTS_MCP_DEFAULT_DIR"
    read -rp "  Path to existing clone (or Enter to clone now): " CUSTOM_PATH
    if [[ -n "$CUSTOM_PATH" ]]; then
      FLIGHTS_MCP_DIR="$CUSTOM_PATH"
    else
      FLIGHTS_MCP_DIR="$FLIGHTS_MCP_DEFAULT_DIR"
      echo "  Cloning $FLIGHTS_MCP_REPO..."
      git clone "$FLIGHTS_MCP_REPO" "$FLIGHTS_MCP_DIR"
    fi
  fi

  echo "  Installing dependencies..."
  uv sync --directory "$FLIGHTS_MCP_DIR" --quiet

  echo "  Registering with Claude..."
  claude mcp add flights --scope user \
    -- uv --directory "$FLIGHTS_MCP_DIR" run flights.py
  green "  Registered 'flights' MCP"
fi

# ── flights-points-tool ───────────────────────────────────────────────────────

step "flights-points MCP server"
if mcp_registered "flights-points"; then
  green "  Already registered as 'flights-points' MCP - skipping"
  yellow "  Note: if SEATS_AERO_API_KEY changed, re-run: claude mcp remove flights-points && ./scripts/install.sh"
else
  echo "  Installing dependencies..."
  uv sync --directory "$FLIGHTS_POINTS_DIR" --quiet

  if [[ "$NO_SCRAPE" == "false" ]]; then
    echo "  Installing browser scraper dependencies..."
    uv sync --directory "$FLIGHTS_POINTS_DIR" --extra scrape --quiet
    if command -v playwright &>/dev/null || uv run --directory "$FLIGHTS_POINTS_DIR" playwright --version &>/dev/null 2>&1; then
      uv run --directory "$FLIGHTS_POINTS_DIR" playwright install chromium --quiet 2>/dev/null || \
        yellow "  Warning: playwright install failed - browser scrapers may not work"
    fi
  fi

  echo "  Registering with Claude..."
  if [[ -n "$SEATS_AERO_API_KEY" ]]; then
    claude mcp add flights-points --scope user \
      -e SEATS_AERO_API_KEY="$SEATS_AERO_API_KEY" \
      -- uv --directory "$FLIGHTS_POINTS_DIR" run python -m flights_points.mcp_server
  else
    claude mcp add flights-points --scope user \
      -- uv --directory "$FLIGHTS_POINTS_DIR" run python -m flights_points.mcp_server
  fi
  green "  Registered 'flights-points' MCP"
fi

# ── find-flights-points skill ─────────────────────────────────────────────────

step "find-flights-points skill"
mkdir -p "$SKILL_DEST"

if [[ -d "$SKILL_SRC" ]]; then
  # Copy from the repo's skill/ directory if it exists
  cp -r "$SKILL_SRC/." "$SKILL_DEST/"
  green "  Installed from $SKILL_SRC"
else
  # Write the skill inline if the skill/ dir doesn't exist yet
  cat > "$SKILL_DEST/SKILL.md" << 'SKILL_EOF'
---
name: find-flights-points
description: Search for the cheapest award flights in points/miles across multiple dates. User specifies origin, destination, and a date range or list of dates. Searches Google Flights for cash prices AND seats.aero/airline sites for real award availability, then ranks dates by cheapest points cost.
---

# Find Flights in Points

Search flights across multiple dates and return award availability (points/miles) alongside cash prices, ranked by cheapest points.

## When to use this skill

The user wants to fly somewhere and pay with points/miles. They give you:
- Origin and destination (city names or IATA codes)
- A date range like "late July", "July 15-22", or specific dates like "July 18 or July 25"
- Optional: preferred cabin class (economy/business/first), number of passengers

## Step 1 - Resolve inputs

Convert any city names to IATA codes (e.g. "Montreal" -> YUL, "Paris" -> CDG). If the user gave a date range, expand it to individual dates. For a range wider than 14 days, sample every 2-3 days rather than every single day to keep results manageable.

Ask for missing required info before proceeding:
- If origin or destination is ambiguous (multiple airports), confirm which one.
- If no dates at all were given, ask for a date range or target window.

## Step 2 - Parallel search across all dates

For EACH date in the expanded list, fire TWO tool calls in parallel (in the same message):

1. `mcp__flights__get_cheapest_flights(origin, destination, departure_date)` - get the cheapest cash price for context
2. `mcp__flights__get_real_points_for_route(origin, destination, departure_date)` - get real award availability

**Critical: launch ALL dates in a single message as parallel tool calls.** Do not do dates one at a time.

Example for 5 dates: one message with 10 tool calls (5 flights + 5 points lookups), all in parallel.

If the date window is very wide (15+ dates), split into two batches of parallel calls.

## Step 3 - Parse and rank results

For each date, extract:
- Cheapest cash price (from flights MCP)
- Lowest award cost per loyalty program (American AAdvantage, United MileagePlus, Delta SkyMiles)
- Note "No availability" if a program has no award seats

Rank the dates by: lowest points across any program (use the minimum across all programs that have availability).

## Step 4 - Present results

Show a summary table ranked by cheapest points:

```
| Date       | Cash Price | AA Miles | United Miles | Delta Miles | Best Value |
|------------|-----------|----------|--------------|-------------|------------|
| 2026-07-18 | $312      | 15,000   | 20,000       | -           | AA 15k     |
| 2026-07-22 | $289      | -        | 17,500       | 18,000      | UA 17.5k   |
| 2026-07-25 | $341      | 22,000   | 22,000       | 20,000      | DL 20k     |
```

Then call out:
- **Best date for points:** which date and which program has the lowest award cost
- **Best cash price:** which date has the cheapest cash fare
- Any dates with no award availability at all across all programs

## Tips

- seats.aero data covers American, United, and Delta without a browser when SEATS_AERO_API_KEY is set.
- Chase Ultimate Rewards transfers to partners - only show Chase if the user asks for it specifically.
- If a program shows "No availability" on all dates, note it once and exclude it from the table.
- Round-trip: run this skill twice (outbound leg, return leg) and present both together.
- Business/first class: pass seat="business" or seat="first" to the flights MCP calls.
SKILL_EOF
  green "  Installed to $SKILL_DEST"
fi

# ── summary ───────────────────────────────────────────────────────────────────

echo ""
green "================================================================"
green " Installation complete!"
green "================================================================"
echo ""
echo "  MCPs registered:"
claude mcp list 2>/dev/null | grep -E "^(flights|flights-points):" | sed 's/^/    /'
echo ""
echo "  Skill installed:"
echo "    $SKILL_DEST/SKILL.md"
echo ""
echo "  Usage in Claude Code:"
echo "    /find-flights-points"
echo "    -> \"Find flights from Montreal to Paris, July 15-25\""
echo ""
if [[ -z "${SEATS_AERO_API_KEY:-}" ]]; then
  yellow "  Tip: set SEATS_AERO_API_KEY for real award data without a browser."
  yellow "  Re-run this script after exporting it, or add -e to the MCP config."
fi
echo ""
yellow "  Restart Claude Code to pick up the new MCP servers."
