# Flights Points Tool

MCP server that looks up **real award availability** (points/miles) for flights via **seats.aero** or airline sites directly. Use it alongside the [Google Flights MCP](https://github.com/smamidipaka6/flights-mcp-server): search flights for cash prices, then call this server to see actual award costs.

Supports **American AAdvantage**, **United MileagePlus**, and **Delta SkyMiles** via seats.aero (no browser needed when API key is set).

## Quick install

```bash
git clone https://github.com/andrew-demers/flights-points-tool
cd flights-points-tool
./scripts/install.sh
```

The script will:
- Check for `uv` and `claude` CLI prerequisites
- Prompt for your seats.aero API key (optional but recommended)
- Clone and register the [Google Flights MCP](https://github.com/smamidipaka6/flights-mcp-server) if not already installed
- Install dependencies and register this MCP server with Claude Code
- Install the `/find-flights-points` skill to your Claude skills directory

After install, restart Claude Code and both MCPs will be available.

**Non-interactive install** (key already in env):
```bash
SEATS_AERO_API_KEY=your-key ./scripts/install.sh
```

**Skip browser scraper install:**
```bash
./scripts/install.sh --no-scrape
```

## Tools

- **`get_real_points_for_route(origin, destination, departure_date, adults?, providers?)`** - Get actual award availability from seats.aero (American, United, Delta) or airline sites via browser scraper. Returns point costs per program or "No availability found" when no award seats exist.

## Skill: `/find-flights-points`

Once installed, use the `/find-flights-points` skill in Claude Code to search across a date range and find the cheapest award flights automatically.

```
/find-flights-points
> Find flights from Montreal to Paris, July 15-25
```

The skill searches all dates in parallel, combines cash prices (Google Flights MCP) with real award availability (this MCP), and returns a ranked table:

```
| Date       | Cash Price | AA Miles | United Miles | Delta Miles | Best Value |
|------------|-----------|----------|--------------|-------------|------------|
| 2026-07-18 | $312      | 15,000   | 20,000       | -           | AA 15k     |
| 2026-07-22 | $289      | -        | 17,500       | 18,000      | UA 17.5k   |
| 2026-07-25 | $341      | 22,000   | 22,000       | 20,000      | DL 20k     |
```

## Data sources

**seats.aero (recommended)** - Set `SEATS_AERO_API_KEY` to get American, United, and Delta award data without a browser. Get an API key at [seats.aero](https://seats.aero) (Pro account required). The install script wires this up automatically.

> **Coverage note:** seats.aero's API uses a cached search that only covers routes it actively monitors - primarily high-demand, high-volume routes. Thin or connecting-only routes (e.g. AUS-AUA, which has no nonstop) may return no results from the API even when seats are available. seats.aero's live search endpoint is not available to Pro API accounts (requires a partner agreement). For routes not in the cache, manual search on seats.aero or airline sites is required.

**seats.aero browser scraper (session-based fallback)** - When the seats.aero API returns no results, the tool falls back to scraping seats.aero directly via a headed Playwright browser using a saved session. This covers thin routes that aren't in the API cache.

Run this once to set up your session (opens a browser window for you to log in):

```bash
uv run python -m flights_points.setup_login
```

Session is saved to `~/.config/flights-points/seats_aero_session.json`. The browser scraper launches automatically on subsequent MCP calls when the session file exists. Set `SEATS_AERO_SESSION_FILE=/custom/path.json` to use a different path.

> **Note:** The browser scraper uses `--disable-blink-features=AutomationControlled` and hides `navigator.webdriver` to bypass basic bot detection on seats.aero. Direct scraping of AA.com, United.com, and Delta.com is not supported - those sites use Cloudflare and behavioral analysis that these flags don't defeat.

## Manual setup

If you prefer to register the MCPs yourself instead of using the install script:

```bash
# Google Flights MCP
claude mcp add flights --scope user \
  -- uv --directory /path/to/flights-mcp-server run flights.py

# flights-points MCP
claude mcp add flights-points --scope user \
  -e SEATS_AERO_API_KEY=your-key \
  -- uv --directory /path/to/flights-points-tool run python -m flights_points.mcp_server
```

Install the skill manually by copying `skill/SKILL.md` to `~/.claude/skills/find-flights-points/SKILL.md`.

## Example agent flow

1. User: "Cheapest flights JFK to LAX next Friday in points"
2. Agent calls `get_cheapest_flights(origin="JFK", destination="LAX", departure_date="2026-02-13")` via Google Flights MCP
3. Agent calls `get_real_points_for_route(origin="JFK", destination="LAX", departure_date="2026-02-13")` via this MCP
4. Agent responds with cash prices and award costs per program side by side

## Development

- Real quote fetchers: `src/flights_points/real_quotes.py`
- Provider scrapers: `src/flights_points/providers/` (seats.aero, American, United, Delta, Chase)
- MCP tools: `src/flights_points/mcp_server.py`
- Skill definition: `skill/SKILL.md`
- Install script: `scripts/install.sh`

Run server locally (stdio): `python -m flights_points.mcp_server`

## License

MIT.
