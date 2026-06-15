# Flights Points Tool

MCP server that converts flight prices to **points/miles equivalents** for **Chase Ultimate Rewards**, **American AAdvantage**, **United MileagePlus**, and **Delta SkyMiles**. Use it alongside the [Google Flights MCP](https://github.com/smamidipaka6/flights-mcp-server): get flight options from Flights MCP, then call this server to see how many points each price is worth.

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
| Delta | SkyMiles | miles | 0.9–1.2–1.5 |

Use `list_point_providers` to see the full bands and notes.

## Tools

- **`get_real_points_for_route(origin, destination, departure_date, adults?, price?, providers?)`** — **Query seats.aero and/or provider sites** for **actual** award points/miles. When **seats.aero** is configured (see below), American, United, and Delta come from its Cached Search API (no browser). Otherwise or on cache miss, optional browser scrapers (aa.com, united.com, delta.com, Chase) are used if `[scrape]` is installed. Chase is always from its scraper or valuation; it may require sign-in.
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

**Real lookups — seats.aero (recommended for American, United & Delta):** No browser needed. Set your [seats.aero](https://seats.aero) Pro API key so American, United, and Delta award miles come from their Cached Search API:

```bash
export SEATS_AERO_API_KEY="your-api-key"
```

Get an API key from [seats.aero](https://seats.aero) → Settings → API (Pro account required; see [their API docs](https://developers.seats.aero/) and [usage limits](https://docs.seats.aero/article/68-do-you-have-an-api)). If the key is set, `get_real_points_for_route` uses seats.aero first for American, United, and Delta; if there’s no cached data or the key is missing, it falls back to browser scrapers when installed.

**Real lookups — browser scrapers (optional):** To also fetch from aa.com, united.com, delta.com, and Chase Travel (or when not using seats.aero), install the optional scrape dependency and Playwright:

```bash
uv sync --extra scrape
# or: pip install -e ".[scrape]"
playwright install chromium
```

Optional: disable individual scrapers via env (e.g. in CI or to avoid browser use):

- `FLIGHTS_POINTS_DISABLE_AA_SCRAPE=1` — American (aa.com)
- `FLIGHTS_POINTS_DISABLE_UNITED_SCRAPE=1` — United (united.com)
- `FLIGHTS_POINTS_DISABLE_DELTA_SCRAPE=1` — Delta (delta.com)
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
        "/Users/andrew/dev/flights-points-tool",
        "run",
        "python",
        "-m",
        "flights_points.mcp_server"
      ]
    }
  }
}
```

Replace `/Users/andrew/dev/flights-points-tool` with the absolute path to this repo. If `uv` is not on your PATH, use the full path to `uv` (e.g. from `which uv`) in `"command"`.

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
        "/Users/andrew/dev/flights-points-tool",
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
3. **Real lookups:** Agent calls `get_real_points_for_route(origin="JFK", destination="LAX", departure_date="2026-02-13", price=299)` → gets American, United, and Delta from **seats.aero** when `SEATS_AERO_API_KEY` is set, and/or from aa.com/united.com/delta.com/Chase when browser scrape is enabled. **Or** use `get_points_equivalent(price="$299")` for valuation-only.
4. Agent responds with flight options and points for each.

## Development

- Valuations: `src/flights_points/valuations.py`
- Real quote fetchers: `src/flights_points/real_quotes.py`, `src/flights_points/providers/` (seats.aero: `seats_aero.py`; American: `american.py`, United: `united.py`, Delta: `delta.py`, Chase: `chase.py` via Playwright)
- MCP tools: `src/flights_points/mcp_server.py`
- Run server locally (stdio): `python -m flights_points.mcp_server`

**Note:** With **seats.aero** you get American, United, and Delta without a browser. Browser scrapers (Playwright) are used when seats.aero isn’t configured or has no data. Chase is only via its scraper or valuation and often requires sign-in. If the seats.aero API response shape changes, `providers/seats_aero.py` may need updates (see [developers.seats.aero](https://developers.seats.aero/reference)).

## License

MIT.
