"""
Real points/miles lookup. Priority order per provider:
1. seats.aero cached API (SEATS_AERO_API_KEY required) — fast, no browser.
2. seats.aero browser scraper — headed Playwright, live search, covers thin/connecting routes.
   Run `uv run python -m flights_points.setup_login` once to save your seats.aero session.

Set FLIGHTS_POINTS_HEADLESS=1 to force headless mode (disables #2 for unauth'd sessions).
"""

from __future__ import annotations

import os
from typing import Any

PROVIDERS = ("american", "united", "delta")


def _fetch_seats_aero(origin: str, destination: str, departure_date: str) -> dict[str, dict[str, Any]]:
    if not os.environ.get("SEATS_AERO_API_KEY"):
        return {}
    try:
        from .providers import seats_aero
        return seats_aero.fetch_from_seats_aero(origin, destination, departure_date)
    except Exception:
        return {}


def _fetch_seats_aero_browser(origin: str, destination: str, departure_date: str) -> dict[str, dict[str, Any]]:
    # Only run if a saved session exists - don't open a login prompt from MCP context
    import pathlib
    session_file = pathlib.Path.home() / ".config" / "flights-points" / "seats_aero_session.json"
    custom = os.environ.get("SEATS_AERO_SESSION_FILE", "").strip()
    if custom:
        session_file = pathlib.Path(custom)
    if not session_file.exists():
        return {}
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
    Query seats.aero for actual award points/miles.
    Returns a dict keyed by provider id with 'points' (list of int or None), 'source', and 'error'.
    No estimate fallback — only real data from seats.aero.
    """
    origin = origin.strip().upper()
    destination = destination.strip().upper()
    if len(origin) != 3 or len(destination) != 3:
        return {}
    del adults  # seats.aero API doesn't filter by passenger count at search time
    providers = provider_ids or list(PROVIDERS)
    results: dict[str, dict[str, Any]] = {}

    # 1. seats.aero cached API — fast, no browser, covers monitored routes
    seats_data = _fetch_seats_aero(origin, destination, departure_date)
    for pid in PROVIDERS:
        if pid in providers and seats_data.get(pid, {}).get("points"):
            results[pid] = seats_data[pid]

    # 2. seats.aero browser — live search via headed browser, covers thin/connecting routes
    missing = [pid for pid in PROVIDERS if pid in providers and not results.get(pid, {}).get("points")]
    if missing:
        browser_data = _fetch_seats_aero_browser(origin, destination, departure_date)
        for pid in missing:
            if browser_data.get(pid, {}).get("points"):
                results[pid] = browser_data[pid]

    return results
