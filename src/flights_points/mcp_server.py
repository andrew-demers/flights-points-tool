"""
MCP server for converting flight prices (e.g. from Google Flights MCP) to points equivalents.
Use alongside the flights-mcp-server: get flight options there, then call these tools for points.
"""

from __future__ import annotations

from .valuations import (
    POINT_PROVIDERS,
    parse_price,
    usd_to_all_providers,
)
from .real_quotes import (
    fetch_real_points_for_route,
    merge_real_with_estimate,
)

from fastmcp import FastMCP

mcp = FastMCP(
    "flights-points",
    instructions="Convert flight prices to points/miles for Chase, American, and United. Use with Google Flights MCP: get flight options from Flights MCP, then call these tools for points equivalents.",
)


def _format_points_result(conversions: list[dict], price_usd: float) -> str:
    lines = [
        f"**Price: ${price_usd:,.2f} USD**",
        "",
        "| Provider | Points range (as price changes) | Typical | Valuation (¢/pt) |",
        "|----------|-------------------------------|---------|------------------|",
    ]
    for c in conversions:
        range_str = f"~{c['points_min']:,}–{c['points_max']:,} {c['unit']}"
        typical_str = f"~{c['points_typical']:,}"
        cpp_str = f"{c['cents_per_point_min']}–{c['cents_per_point_max']} (typ. {c['cents_per_point_typical']:.2f})"
        lines.append(
            f"| {c['name']} | {range_str} | {typical_str} | {cpp_str} |"
        )
    lines.append("")
    lines.append("_Points update as price changes; programs don’t use a fixed points-per-dollar._")
    return "\n".join(lines)


@mcp.tool()
def get_points_equivalent(
    price: str | int | float,
    providers: str | None = None,
) -> str:
    """
    Convert a flight price to the approximate points or miles needed for Chase, American, and United.
    Returns a *range* for each program (points path style): points update as price changes, and
    programs like American don't use a fixed points-per-dollar, so you get min–max and a typical value.

    Use this after getting flight options from the Google Flights MCP: take the price from any
    flight (e.g. "$299" or 299) and get the points equivalent for each program.

    Args:
        price: Flight price in USD. Can be a number (e.g. 299) or a string like "$299" or "$1,234".
        providers: Optional comma-separated list to limit results. Options: chase, american, united.
                   Default is all three.

    Returns:
        A formatted table with points range, typical value, and valuation band for each provider.
    """
    price_usd = parse_price(price)
    if price_usd is None:
        return "Invalid price. Use a number (e.g. 299) or a string like \"$299\" or \"$1,234\"."

    provider_list = None
    if providers:
        provider_list = [p.strip().lower() for p in providers.split(",") if p.strip()]
        invalid = [p for p in provider_list if p not in POINT_PROVIDERS]
        if invalid:
            return f"Unknown provider(s): {', '.join(invalid)}. Use: chase, american, united."

    conversions = usd_to_all_providers(price_usd, provider_list)
    if not conversions:
        return "No conversions computed. Check the price and providers."

    return _format_points_result(conversions, price_usd)


@mcp.tool()
def get_points_for_multiple_prices(
    prices: list[str | int | float],
    providers: str | None = None,
) -> str:
    """
    Convert multiple flight prices to points equivalents in one call.

    Useful when you have several options from the Flights MCP (e.g. cheapest flights or best flights).
    Pass a list of prices; each can be a number or a string like "$299".

    Args:
        prices: List of flight prices in USD (e.g. [299, "$450", "$1,234.56"]).
        providers: Optional comma-separated list: chase, american, united. Default is all.

    Returns:
        A formatted section per valid price with points for each provider.
    """
    provider_list = None
    if providers:
        provider_list = [p.strip().lower() for p in providers.split(",") if p.strip()]
        invalid = [p for p in provider_list if p not in POINT_PROVIDERS]
        if invalid:
            return f"Unknown provider(s): {', '.join(invalid)}. Use: chase, american, united."

    sections = []
    for i, price in enumerate(prices):
        price_usd = parse_price(price)
        if price_usd is None:
            sections.append(f"**Option {i + 1}:** Invalid price: {price!r}")
            continue
        conversions = usd_to_all_providers(price_usd, provider_list)
        if conversions:
            sections.append(_format_points_result(conversions, price_usd))
        else:
            sections.append(f"**Option {i + 1}:** No conversions for ${price_usd}.")

    return "\n\n---\n\n".join(sections) if sections else "No valid prices provided."


def _format_real_points_result(merged: list[dict], route: str, date: str, price_usd: float | None) -> str:
    lines = [
        f"**Route:** {route} — **Date:** {date}",
        f"**Real-time lookups** from provider sites (when available); otherwise valuation-based estimate.",
        "",
        "| Provider | Source | Points |",
        "|----------|--------|--------|",
    ]
    for m in merged:
        if m.get("source") == "real":
            pts = m["points_list"]
            if len(pts) == 1:
                pt_str = f"{pts[0]:,} {m['unit']}"
            else:
                pt_str = f"{m['points_min']:,}–{m['points_max']:,} {m['unit']} ({len(pts)} options)"
            lines.append(f"| {m['name']} | {m.get('site', '—')} | {pt_str} |")
        elif m.get("source") == "estimate":
            pt_str = f"~{m['points_typical']:,} {m['unit']} (estimate)"
            lines.append(f"| {m['name']} | {m.get('site', '—')} | {pt_str} |")
        else:
            err = m.get("error", "No data")
            lines.append(f"| {m['name']} | — | {err} |")
    if price_usd is not None and price_usd > 0:
        lines.append("")
        lines.append(f"_Estimate fallback uses cash price ${price_usd:,.2f}. For other prices use get_points_equivalent(price)._")
    else:
        lines.append("")
        lines.append("_To see valuation-based estimates, use get_points_equivalent(price) with the flight’s cash price._")
    return "\n".join(lines)


@mcp.tool()
def get_real_points_for_route(
    origin: str,
    destination: str,
    departure_date: str,
    adults: int = 1,
    price: str | int | float | None = None,
    providers: str | None = None,
) -> str:
    """
    Get actual points/miles for a route and date by querying Chase, American (aa.com), and United.

    Calls each provider's site when the optional [scrape] dependency (playwright) is installed.
    Chase Travel may require sign-in and can return a message instead of points. If a provider
    fails or is disabled, pass an optional cash price to see a valuation-based estimate for that program.

    Use with the same origin, destination, and date as the Google Flights MCP so you can compare
    real award costs to cash prices.

    Args:
        origin: Origin airport IATA code (e.g. "JFK", "LAX").
        destination: Destination airport IATA code (e.g. "LAX", "LHR").
        departure_date: Departure date YYYY-MM-DD.
        adults: Number of adults (default 1).
        price: Optional cash price in USD (e.g. 299 or "$299"). If provided, used as fallback
               estimate for providers that don't support real-time lookup (Chase, United).
        providers: Optional comma-separated list: chase, american, united. Default all.

    Returns:
        Table of real points (from provider sites) or estimates per program.
    """
    origin = origin.strip().upper()
    destination = destination.strip().upper()
    if len(origin) != 3 or len(destination) != 3:
        return "Origin and destination must be 3-letter IATA codes (e.g. JFK, LAX)."
    if len(departure_date) != 10 or departure_date[4] != "-" or departure_date[7] != "-":
        return "Departure date must be YYYY-MM-DD."

    price_usd = parse_price(price) if price is not None else None
    provider_list = None
    if providers:
        provider_list = [p.strip().lower() for p in providers.split(",") if p.strip()]
        invalid = [p for p in provider_list if p not in POINT_PROVIDERS]
        if invalid:
            return f"Unknown provider(s): {', '.join(invalid)}. Use: chase, american, united."

    real_results = fetch_real_points_for_route(
        origin, destination, departure_date, adults=adults, provider_ids=provider_list
    )
    merged = merge_real_with_estimate(real_results, price_usd, provider_list)
    route_str = f"{origin} → {destination}"
    return _format_real_points_result(merged, route_str, departure_date, price_usd)


@mcp.tool()
def list_point_providers() -> str:
    """
    List the supported point providers and their valuation range (min–typical–max cents per point).
    Points are shown as a range because programs don't use a fixed points-per-dollar.
    """
    lines = [
        "| Provider | Name | Unit | Cents/point (min–typical–max) | Notes |",
        "|----------|------|------|--------------------------------|-------|",
    ]
    for pid, p in POINT_PROVIDERS.items():
        cpp = f"{p['cents_per_point_min']}–{p['cents_per_point_typical']}–{p['cents_per_point_max']}"
        lines.append(
            f"| {pid} | {p['name']} | {p['unit']} | {cpp} | {p['notes']} |"
        )
    return "\n".join(lines)


def run_server() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    run_server()
