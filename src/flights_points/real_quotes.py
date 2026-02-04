"""
Real points/miles lookup by querying provider sites (aa.com, Chase, United).

When available, returns actual award costs for a route+date instead of
valuation-based estimates. Requires optional dependency 'playwright' for
all three; set FLIGHTS_POINTS_DISABLE_*_SCRAPE=1 to disable per provider.
"""

from __future__ import annotations

import os
from typing import Any

from .valuations import POINT_PROVIDERS, usd_to_all_providers


def _fetch_american(origin: str, destination: str, departure_date: str, adults: int = 1) -> dict[str, Any] | None:
    if os.environ.get("FLIGHTS_POINTS_DISABLE_AA_SCRAPE", "").lower() in ("1", "true", "yes"):
        return None
    try:
        from .providers import american
        return american.fetch_award_miles(origin, destination, departure_date, adults)
    except Exception:
        return None


def _fetch_chase(origin: str, destination: str, departure_date: str, adults: int = 1) -> dict[str, Any] | None:
    if os.environ.get("FLIGHTS_POINTS_DISABLE_CHASE_SCRAPE", "").lower() in ("1", "true", "yes"):
        return {"source": "chase.com", "points": None, "error": "Chase scrape disabled by FLIGHTS_POINTS_DISABLE_CHASE_SCRAPE."}
    try:
        from .providers import chase
        return chase.fetch_award_points(origin, destination, departure_date, adults)
    except Exception:
        return {"source": "chase.com", "points": None, "error": "Chase Travel lookup failed (install [scrape] and playwright?)."}


def _fetch_united(origin: str, destination: str, departure_date: str, adults: int = 1) -> dict[str, Any] | None:
    if os.environ.get("FLIGHTS_POINTS_DISABLE_UNITED_SCRAPE", "").lower() in ("1", "true", "yes"):
        return None
    try:
        from .providers import united
        return united.fetch_award_miles(origin, destination, departure_date, adults)
    except Exception:
        return None


FETCHERS = {
    "american": _fetch_american,
    "chase": _fetch_chase,
    "united": _fetch_united,
}


def fetch_real_points_for_route(
    origin: str,
    destination: str,
    departure_date: str,
    adults: int = 1,
    provider_ids: list[str] | None = None,
) -> dict[str, dict[str, Any]]:
    """
    Query each provider's site for actual award points/miles on the given route and date.
    Returns a dict keyed by provider id with 'points' (list of int or None), 'source', and optional 'error'.
    """
    origin = origin.strip().upper()
    destination = destination.strip().upper()
    if len(origin) != 3 or len(destination) != 3:
        return {}
    providers = provider_ids or list(FETCHERS)
    results = {}
    for pid in providers:
        if pid not in FETCHERS:
            continue
        try:
            out = FETCHERS[pid](origin, destination, departure_date, adults)
            if out is not None:
                results[pid] = out
        except Exception as e:
            results[pid] = {"source": pid, "points": None, "error": str(e)}
    return results


def merge_real_with_estimate(
    real_results: dict[str, dict[str, Any]],
    price_usd: float | None,
    provider_ids: list[str] | None = None,
) -> list[dict[str, Any]]:
    """
    Build a unified view: use real points when available, otherwise valuation-based estimate if price_usd given.
    real_results: from fetch_real_points_for_route().
    price_usd: if provided, used for estimate fallback for providers with no real data.
    provider_ids: if provided, only include these providers.
    """
    providers = provider_ids or list(POINT_PROVIDERS)
    merged = []
    for pid in providers:
        meta = POINT_PROVIDERS.get(pid)
        if not meta:
            continue
        name = meta["name"]
        unit = meta["unit"]
        entry = {"provider": pid, "name": name, "unit": unit}
        real = real_results.get(pid)
        if real and real.get("points"):
            pts = real["points"]
            entry["source"] = "real"
            entry["points_list"] = pts
            entry["points_min"] = min(pts)
            entry["points_max"] = max(pts)
            entry["points_typical"] = round(sum(pts) / len(pts))
            entry["site"] = real.get("source", pid)
        elif price_usd is not None and price_usd > 0:
            conv = usd_to_all_providers(price_usd, [pid])
            if conv:
                c = conv[0]
                entry["source"] = "estimate"
                entry["points_min"] = c["points_min"]
                entry["points_max"] = c["points_max"]
                entry["points_typical"] = c["points_typical"]
                entry["site"] = "valuation (no real lookup)"
            else:
                entry["source"] = "unavailable"
                entry["error"] = real.get("error", "No data") if real else "Not queried"
        else:
            entry["source"] = "unavailable"
            entry["error"] = real.get("error", "No data") if real else "Not queried"
        merged.append(entry)
    return merged
