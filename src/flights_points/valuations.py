"""
Points/miles valuations for flight price conversion.

Uses a "points path" style: points are shown as a range that updates as price
changes, because programs like American don't use a fixed points-per-dollar
(redemption value varies by route, cabin, and availability).
"""

from __future__ import annotations

# Min / typical / max cents per point (cpp). Range reflects real variation in redemptions.
# points_min = price_usd * 100 / cpp_max  (best redemption)
# points_max = price_usd * 100 / cpp_min  (weaker redemption)
POINT_PROVIDERS = {
    "chase": {
        "name": "Chase Ultimate Rewards",
        "unit": "points",
        "cents_per_point_min": 1.6,   # e.g. portal or weaker transfer
        "cents_per_point_typical": 2.05,
        "cents_per_point_max": 2.5,   # strong transfer redemptions
        "notes": "Value varies by transfer partner or Chase Travel use.",
    },
    "american": {
        "name": "American AAdvantage",
        "unit": "miles",
        "cents_per_point_min": 1.0,   # economy, low availability
        "cents_per_point_typical": 1.2,
        "cents_per_point_max": 1.5,   # economy saver / partner; premium higher
        "notes": "Points per dollar vary by route, dates, and cabin.",
    },
    "united": {
        "name": "United MileagePlus",
        "unit": "miles",
        "cents_per_point_min": 1.0,
        "cents_per_point_typical": 1.2,
        "cents_per_point_max": 1.5,
        "notes": "Value varies by award availability and Star Alliance partners.",
    },
}


def _effective_typical_cpp(price_usd: float, provider: dict) -> float:
    """
    Dynamic typical cpp that can shift with price (e.g. American often has
    different effective value on very low vs higher fares).
    """
    low = provider["cents_per_point_min"]
    mid = provider["cents_per_point_typical"]
    high = provider["cents_per_point_max"]
    # Slight price-based shift: very low fares often worse cpp, higher fares can be better
    if price_usd < 150:
        return mid * 0.95
    if price_usd > 600:
        return min(mid * 1.05, high)
    # Linear blend between 150–600
    t = (price_usd - 150) / 450.0
    return mid * (0.95 + 0.10 * t)


def parse_price(price_input: str | int | float) -> float | None:
    """
    Parse a price from string (e.g. '$299', '$1,234.56') or numeric value.
    Returns price in USD as a float, or None if unparseable.
    """
    if isinstance(price_input, (int, float)):
        return float(price_input) if price_input >= 0 else None
    if not isinstance(price_input, str):
        return None
    s = price_input.strip().replace("$", "").replace(",", "").strip()
    if not s:
        return None
    try:
        val = float(s)
        return val if val >= 0 else None
    except ValueError:
        return None


def usd_to_points(price_usd: float, provider_id: str) -> dict | None:
    """
    Convert a USD price to approximate points/miles needed for one provider.
    Returns a range (min–max) and a price-dependent typical value so points
    "move" as price changes (points-path style).
    """
    if price_usd < 0:
        return None
    provider = POINT_PROVIDERS.get(provider_id.lower())
    if not provider:
        return None
    cpp_min = provider["cents_per_point_min"]
    cpp_max = provider["cents_per_point_max"]
    cpp_typical = _effective_typical_cpp(price_usd, provider)
    # Fewer points needed when cpp is higher (better redemption)
    points_min = (price_usd * 100) / cpp_max
    points_max = (price_usd * 100) / cpp_min
    points_typical = (price_usd * 100) / cpp_typical
    return {
        "provider": provider_id.lower(),
        "name": provider["name"],
        "unit": provider["unit"],
        "cents_per_point_min": cpp_min,
        "cents_per_point_typical": cpp_typical,
        "cents_per_point_max": cpp_max,
        "points_min": round(points_min),
        "points_max": round(points_max),
        "points_typical": round(points_typical),
        "price_usd": round(price_usd, 2),
    }


def usd_to_all_providers(price_usd: float, provider_ids: list[str] | None = None) -> list[dict]:
    """
    Convert a USD price to points for all (or selected) providers.
    Each result includes a range (points_min–points_max) and a price-dependent typical.
    """
    if price_usd < 0:
        return []
    ids = (provider_ids or list(POINT_PROVIDERS)).copy()
    result = []
    for pid in ids:
        conv = usd_to_points(price_usd, pid)
        if conv:
            result.append(conv)
    return result
