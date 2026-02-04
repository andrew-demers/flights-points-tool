# Flights Points Tool

MCP server that converts flight prices to **points/miles equivalents** for **Chase Ultimate Rewards**, **American AAdvantage**, and **United MileagePlus**. Use it alongside the [Google Flights MCP](https://github.com/smamidipaka6/flights-mcp-server): get flight options from Flights MCP, then call this server to see how many points each price is worth.

## Points-path style: ranges that update with price

Points are shown as **ranges** (e.g. ~20,000–30,000 miles) that **update as the price changes**, because programs like American don’t use a fixed points-per-dollar—redemption value varies by route, dates, and cabin. Each result includes:

- **Range** — min–max points for that price (from the program’s valuation band).
- **Typical** — a price-dependent typical value (slightly different for very low vs higher fares).

## Point providers and valuation bands

| Provider | Program | Unit | Cents/point (min–typical–max) |
|----------|---------|------|-------------------------------|
| Chase | Ultimate Rewards | points | 1.6–2.05–2.5 |
| American | AAdvantage | miles | 1.0–1.2–1.5 |
| United | MileagePlus | miles | 1.0–1.2–1.5 |

Use `list_point_providers` to see the full bands and notes.

## Tools

- **`get_real_points_for_route(origin, destination, departure_date, adults?, price?, providers?)`** — **Query provider sites** (aa.com, Chase, United) for **actual** award points/miles on that route and date. When a site is queried successfully you see real costs; otherwise you get a valuation-based estimate if you pass an optional cash `price`. All three use the optional `[scrape]` dependency (see below). Chase Travel may require sign-in and can return a message to that effect.
- **`get_points_equivalent(price, providers?)`** — Convert a **cash price** to a points range and typical value (valuation-based). Price can be `"$299"` or `299`.
- **`get_points_for_multiple_prices(prices, providers?)`** — Same for a list of prices (e.g. from Flights MCP cheapest/best results).
- **`list_point_providers()`** — List programs and their min–typical–max valuation (cents per point).

## Setup

### Install

```bash
cd /path/to/flights-points-tool
uv sync
# or: pip install -e .
```

**Real lookups (American, United, Chase):** To fetch actual points/miles from aa.com, united.com, and Chase Travel, install the optional scrape dependency and Playwright’s browser:

```bash
uv sync --extra scrape
# or: pip install -e ".[scrape]"
playwright install chromium
```

Optional: disable individual scrapers via env (e.g. in CI or to avoid browser use):

- `FLIGHTS_POINTS_DISABLE_AA_SCRAPE=1` — American (aa.com)
- `FLIGHTS_POINTS_DISABLE_UNITED_SCRAPE=1` — United (united.com)
- `FLIGHTS_POINTS_DISABLE_CHASE_SCRAPE=1` — Chase Travel (chase.com/travel; often requires sign-in)

### Run with Cursor

1. **Project MCP**: Create or edit `.cursor/mcp.json` in this repo (or your project that uses it):

```json
{
  "mcpServers": {
    "flights-points": {
      "command": "uv",
      "args": [
        "--directory",
        "/Users/huxley-47/dev/flights-points-tool",
        "run",
        "python",
        "-m",
        "flights_points.mcp_server"
      ]
    }
  }
}
```

Replace `/Users/huxley-47/dev/flights-points-tool` with the absolute path to this repo. If `uv` is not on your PATH, use the full path to `uv` (e.g. from `which uv`) in `"command"`.

2. **With Google Flights MCP**: Add the Flights MCP in the same `mcp.json` so the agent can both search flights and get points:

```json
{
  "mcpServers": {
    "flights": {
      "command": "uv",
      "args": [
        "--directory",
        "/path/to/flights-mcp-server",
        "run",
        "flights.py"
      ]
    },
    "flights-points": {
      "command": "uv",
      "args": [
        "--directory",
        "/Users/huxley-47/dev/flights-points-tool",
        "run",
        "python",
        "-m",
        "flights_points.mcp_server"
      ]
    }
  }
}
```

3. Restart Cursor (or reload MCP) so both servers are available.

## Example agent flow

1. User: “Cheapest flights JFK to LAX next Friday, and how many points?”
2. Agent calls Flights MCP: `get_cheapest_flights(origin="JFK", destination="LAX", departure_date="2026-02-13")` → gets list of flights with prices like `"$299"`, `"$312"`, …
3. **Real lookups:** Agent calls `get_real_points_for_route(origin="JFK", destination="LAX", departure_date="2026-02-13", price=299)` → gets actual miles/points from aa.com, united.com, and Chase Travel when scrape is enabled (Chase may require sign-in). **Or** use `get_points_equivalent(price="$299")` for valuation-only.
4. Agent responds with flight options and points for each.

## Development

- Valuations: `src/flights_points/valuations.py`
- Real quote fetchers: `src/flights_points/real_quotes.py`, `src/flights_points/providers/` (American: `american.py`, United: `united.py`, Chase: `chase.py`, all via Playwright)
- MCP tools: `src/flights_points/mcp_server.py`
- Run server locally (stdio): `python -m flights_points.mcp_server`

**Note:** Real lookups use browser automation (Playwright). Chase Travel often requires sign-in, so that scraper may return a message instead of points. Site changes can break selectors; report issues if a provider stops returning results.

## License

MIT.
