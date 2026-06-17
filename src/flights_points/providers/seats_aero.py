"""
seats.aero Cached Search API for American, United, and Delta award miles.

Uses the Pro API (Cached Search). Set SEATS_AERO_API_KEY in the environment.
See https://developers.seats.aero/ and https://docs.seats.aero/article/68-do-you-have-an-api
"""

from __future__ import annotations

import os
from typing import Any

BASE_URL = "https://seats.aero/partnerapi"

PROGRAM_MAP = {
    "aadvantage": "american",
    "american": "american",
    "aa": "american",
    "mileageplus": "united",
    "united": "united",
    "ua": "united",
    "skymiles": "delta",
    "delta": "delta",
    "dl": "delta",
}

# Cabin availability/cost field pairs in seats.aero response
_CABINS = [
    ("YAvailable", "YMileageCost"),
    ("WAvailable", "WMileageCost"),
    ("JAvailable", "JMileageCost"),
    ("FAvailable", "FMileageCost"),
]


def _normalize_program(name: str) -> str | None:
    if not name:
        return None
    return PROGRAM_MAP.get(name.lower().strip())


def _extract_miles_from_response(data: Any) -> dict[str, list[int]]:
    """
    Parse seats.aero API response into { provider_id -> sorted list of mile costs }.

    The API returns { "data": [ { "Route": { "Source": "american" }, "YMileageCost": "13500",
    "YAvailable": true, "JMileageCost": "40000", "JAvailable": true, ... } ] }
    """
    out: dict[str, list[int]] = {}
    if not isinstance(data, dict):
        return out
    items = data.get("data")
    if not isinstance(items, list):
        return out
    for item in items:
        if not isinstance(item, dict):
            continue
        route = item.get("Route") or {}
        source = route.get("Source") or item.get("source") or item.get("Source") or ""
        pid = _normalize_program(source)
        if pid not in ("american", "united", "delta"):
            continue
        for avail_field, cost_field in _CABINS:
            if item.get(avail_field):
                raw = item.get(cost_field)
                try:
                    m = int(raw)
                    if 1_000 <= m <= 500_000:
                        out.setdefault(pid, []).append(m)
                except (TypeError, ValueError):
                    pass
    for k in out:
        out[k] = sorted(set(out[k]))
    return out


def fetch_from_seats_aero(
    origin: str,
    destination: str,
    departure_date: str,
    api_key: str | None = None,
) -> dict[str, dict[str, Any]]:
    """
    Call seats.aero Cached Search and return results keyed by provider id (american, united, delta).
    Returns e.g. { "american": { "source": "seats.aero", "points": [13500, 40000] }, ... }.
    Empty dict if no API key; error entries on failure.
    """
    key = (api_key or os.environ.get("SEATS_AERO_API_KEY") or "").strip()
    if not key:
        return {}

    origin = origin.strip().upper()
    destination = destination.strip().upper()
    if len(origin) != 3 or len(destination) != 3:
        return {}
    if len(departure_date) != 10 or departure_date[4] != "-" or departure_date[7] != "-":
        return {}

    params = {
        "origin_airport": origin,
        "destination_airport": destination,
        "start_date": departure_date,
        "end_date": departure_date,
    }
    url = f"{BASE_URL}/search"

    try:
        import ssl
        import httpx
        import truststore
        ssl_ctx = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        with httpx.Client(timeout=15, verify=ssl_ctx) as client:
            resp = client.get(url, params=params, headers={"Partner-Authorization": key, "Accept": "application/json"})
        if resp.status_code >= 400:
            err = f"seats.aero API error {resp.status_code}: {resp.text[:200]}"
            return {pid: {"source": "seats.aero", "points": None, "error": err} for pid in ("american", "united", "delta")}
        data = resp.json()
    except Exception as e:
        err = str(e)
        return {pid: {"source": "seats.aero", "points": None, "error": err} for pid in ("american", "united", "delta")}

    by_provider = _extract_miles_from_response(data)
    results = {}
    for pid in ("american", "united", "delta"):
        if by_provider.get(pid):
            results[pid] = {"source": "seats.aero", "points": by_provider[pid], "error": None}
        else:
            results[pid] = {"source": "seats.aero", "points": None, "error": "No availability in cached data for this route/date."}
    return results
