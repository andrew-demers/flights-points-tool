"""
Real points/miles lookup. Priority order per provider:
1. seats.aero cached API (SEATS_AERO_API_KEY required) — fast, no browser.
2. seats.aero browser scraper — headed Playwright, live search, covers thin/connecting routes.
3. Individual airline sites (aa.com, united.com, delta.com) — headed Playwright fallback.

Set FLIGHTS_POINTS_HEADLESS=1 to force headless mode (disables #2 for unauth'd sessions).
Set FLIGHTS_POINTS_DISABLE_*_SCRAPE=1 to skip individual airline scrapers.
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


def _fetch_seats_aero_browser(origin: str, destination: str, departure_date: str) -> dict[str, dict[str, Any]]:
    try:
        from .providers import seats_aero_browser
        return seats_aero_browser.fetch_from_seats_aero_browser(origin, destination, departure_date)
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

    # 1. seats.aero cached API — fast, no browser, covers monitored routes
    seats_data = _fetch_seats_aero(origin, destination, departure_date)
    for pid in ("american", "united", "delta"):
        if pid in providers and seats_data.get(pid, {}).get("points"):
            results[pid] = seats_data[pid]

    # 2. seats.aero browser — live search via headed browser, covers thin/connecting routes
    missing = [pid for pid in ("american", "united", "delta") if pid in providers and not results.get(pid, {}).get("points")]
    if missing:
        browser_data = _fetch_seats_aero_browser(origin, destination, departure_date)
        for pid in missing:
            if browser_data.get(pid, {}).get("points"):
                results[pid] = browser_data[pid]

    # 3. Individual airline sites — fallback for anything still missing
    for pid in providers:
        if pid not in _SCRAPERS:
            continue
        if results.get(pid, {}).get("points"):
            continue
        out = _SCRAPERS[pid](origin, destination, departure_date, adults)
        if out is not None:
            results[pid] = out

    return results
