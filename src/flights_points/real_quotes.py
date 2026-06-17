"""
Real points/miles lookup by querying seats.aero (preferred) or provider sites via Playwright.

Data sources:
- seats.aero (preferred): set SEATS_AERO_API_KEY for American, United, and Delta.
- Browser scrapers (fallback): install [scrape] + playwright for aa.com, united.com, delta.com, Chase.
  Set FLIGHTS_POINTS_DISABLE_*_SCRAPE=1 to disable per provider.
"""

from __future__ import annotations

import os
from typing import Any

PROVIDERS = ("american", "united", "delta", "chase")


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
        return {"source": "chase.com", "points": None, "error": "Chase scrape disabled."}
    try:
        from .providers import chase
        return chase.fetch_award_points(origin, destination, departure_date, adults)
    except Exception:
        return {"source": "chase.com", "points": None, "error": "Chase lookup failed (install [scrape] and playwright?)."}


def _fetch_united(origin: str, destination: str, departure_date: str, adults: int = 1) -> dict[str, Any] | None:
    if os.environ.get("FLIGHTS_POINTS_DISABLE_UNITED_SCRAPE", "").lower() in ("1", "true", "yes"):
        return None
    try:
        from .providers import united
        return united.fetch_award_miles(origin, destination, departure_date, adults)
    except Exception:
        return None


def _fetch_delta(origin: str, destination: str, departure_date: str, adults: int = 1) -> dict[str, Any] | None:
    if os.environ.get("FLIGHTS_POINTS_DISABLE_DELTA_SCRAPE", "").lower() in ("1", "true", "yes"):
        return None
    try:
        from .providers import delta
        return delta.fetch_award_miles(origin, destination, departure_date, adults)
    except Exception:
        return None


_SCRAPERS = {
    "american": _fetch_american,
    "chase": _fetch_chase,
    "united": _fetch_united,
    "delta": _fetch_delta,
}


def _fetch_seats_aero(origin: str, destination: str, departure_date: str) -> dict[str, dict[str, Any]]:
    if not os.environ.get("SEATS_AERO_API_KEY"):
        return {}
    try:
        from .providers import seats_aero
        return seats_aero.fetch_from_seats_aero(origin, destination, departure_date)
    except Exception:
        return {}


def fetch_real_points_for_route(
    origin: str,
    destination: str,
    departure_date: str,
    adults: int = 1,
    provider_ids: list[str] | None = None,
) -> dict[str, dict[str, Any]]:
    """
    Query seats.aero (if API key set) and/or each provider's site for actual award points/miles.
    Returns a dict keyed by provider id with 'points' (list of int or None), 'source', and 'error'.
    No estimate fallback — only real data from seats.aero or scrapers.
    """
    origin = origin.strip().upper()
    destination = destination.strip().upper()
    if len(origin) != 3 or len(destination) != 3:
        return {}
    providers = provider_ids or list(PROVIDERS)
    results: dict[str, dict[str, Any]] = {}

    # seats.aero covers american, united, delta — prefer it when key is set
    seats_data = _fetch_seats_aero(origin, destination, departure_date)
    for pid in ("american", "united", "delta"):
        if pid in providers and seats_data.get(pid, {}).get("points"):
            results[pid] = seats_data[pid]

    # Fall back to scrapers for any provider without data yet
    for pid in providers:
        if pid not in _SCRAPERS:
            continue
        if results.get(pid, {}).get("points"):
            continue
        out = _SCRAPERS[pid](origin, destination, departure_date, adults)
        if out is not None:
            results[pid] = out

    return results
