"""
MCP server for looking up real award points/miles for flights.
Queries seats.aero (preferred, requires SEATS_AERO_API_KEY) or provider sites via Playwright.
"""

from __future__ import annotations

from .real_quotes import fetch_real_points_for_route, PROVIDERS

from fastmcp import FastMCP

mcp = FastMCP(
    "flights-points",
    instructions="Look up real award availability (points/miles) for flights via seats.aero or airline sites. Use with Google Flights MCP: get flight options from Flights MCP, then call get_real_points_for_route for actual award costs.",
)

_PROVIDER_NAMES = {
    "american": ("American AAdvantage", "miles"),
    "united": ("United MileagePlus", "miles"),
    "delta": ("Delta SkyMiles", "miles"),
}


def _format_result(results: dict, route: str, date: str) -> str:
    lines = [
        f"**Route:** {route} — **Date:** {date}",
        "",
        "| Provider | Points / Miles | Source |",
        "|----------|----------------|--------|",
    ]
    for pid in PROVIDERS:
        name, unit = _PROVIDER_NAMES.get(pid, (pid, "points"))
        r = results.get(pid)
        if r and r.get("points"):
            pts = r["points"]
            if len(pts) == 1:
                pt_str = f"{pts[0]:,} {unit}"
            else:
                pt_str = f"{min(pts):,}–{max(pts):,} {unit} ({len(pts)} options)"
            lines.append(f"| {name} | {pt_str} | {r.get('source', '—')} |")
        else:
            err = (r or {}).get("error") or "No availability found"
            lines.append(f"| {name} | — | {err} |")
    return "\n".join(lines)


@mcp.tool()
def get_real_points_for_route(
    origin: str,
    destination: str,
    departure_date: str,
    adults: int = 1,
    providers: str | None = None,
) -> str:
    """
    Get actual award points/miles for a route and date from seats.aero or airline sites.

    Uses seats.aero Cached Search API (set SEATS_AERO_API_KEY) for American, United, and Delta.
    Falls back to browser scrapers (requires [scrape] install + playwright) if seats.aero has no data
    or is not configured. Returns "No availability found" when neither source has data.

    Use with the same origin, destination, and date as the Google Flights MCP to compare
    real award costs to cash prices.

    Args:
        origin: Origin airport IATA code (e.g. "JFK", "LAX").
        destination: Destination airport IATA code (e.g. "LAX", "LHR").
        departure_date: Departure date YYYY-MM-DD.
        adults: Number of adults (default 1).
        providers: Optional comma-separated list: american, united, delta. Default all.

    Returns:
        Table of award availability per program. No data = no availability found from any source.
    """
    origin = origin.strip().upper()
    destination = destination.strip().upper()
    if len(origin) != 3 or len(destination) != 3:
        return "Origin and destination must be 3-letter IATA codes (e.g. JFK, LAX)."
    if len(departure_date) != 10 or departure_date[4] != "-" or departure_date[7] != "-":
        return "Departure date must be YYYY-MM-DD."

    provider_list = None
    if providers:
        provider_list = [p.strip().lower() for p in providers.split(",") if p.strip()]
        invalid = [p for p in provider_list if p not in _PROVIDER_NAMES]
        if invalid:
            return f"Unknown provider(s): {', '.join(invalid)}. Use: american, united, delta, chase."

    results = fetch_real_points_for_route(
        origin, destination, departure_date, adults=adults, provider_ids=provider_list
    )
    route_str = f"{origin} → {destination}"
    return _format_result(results, route_str, departure_date)


def run_server() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    run_server()
