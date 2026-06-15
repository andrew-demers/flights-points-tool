"""
seats.aero Cached Search API for American and United award miles.

Uses the Pro API (Cached Search). Set SEATS_AERO_API_KEY in the environment.
See https://developers.seats.aero/ and https://docs.seats.aero/article/68-do-you-have-an-api
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

BASE_URL = "https://seats.aero/partnerapi"
# Map seats.aero program identifiers to our provider ids (lowercase)
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


def _normalize_program(name: str) -> str | None:
    if not name:
        return None
    key = name.lower().strip()
    return PROGRAM_MAP.get(key)


def _extract_miles_from_response(data: Any) -> dict[str, list[int]]:
    """
    Extract (provider -> list of miles) from seats.aero API response.
    Handles common shapes: { "data": [ { "program", "miles" } ] }, { "results": [...] }, etc.
    """
    out: dict[str, list[int]] = {}
    if not isinstance(data, dict):
        return out
    # Prefer "data" or "results" or "flights" array
    items = data.get("data") or data.get("results") or data.get("flights") or data.get("availability")
    if isinstance(items, list):
        for item in items:
            if not isinstance(item, dict):
                continue
            program = item.get("program") or item.get("programId") or item.get("programName") or item.get("source")
            miles = item.get("miles") or item.get("points") or item.get("cost") or item.get("mileageCost")
            if miles is not None and program is not None:
                pid = _normalize_program(str(program))
                if pid and pid in ("american", "united", "delta"):
                    try:
                        m = int(miles)
                        if 1_000 <= m <= 500_000:
                            out.setdefault(pid, []).append(m)
                    except (TypeError, ValueError):
                        pass
    # Also check top-level array
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                program = item.get("program") or item.get("programId")
                miles = item.get("miles") or item.get("points") or item.get("cost")
                if miles is not None and program is not None:
                    pid = _normalize_program(str(program))
                    if pid and pid in ("american", "united", "delta"):
                        try:
                            m = int(miles)
                            if 1_000 <= m <= 500_000:
                                out.setdefault(pid, []).append(m)
                        except (TypeError, ValueError):
                            pass
    # Dedupe and sort per provider
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
    Call seats.aero Cached Search and return results keyed by our provider id (american, united).
    Returns e.g. { "american": { "source": "seats.aero", "points": [25000, 32000] }, "united": { ... } }.
    Empty dict or only error entries if no API key or request fails.
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

    # Cached Search: GET with origin, destination, startDate, endDate
    # If the API uses different param names (e.g. from/to), see developers.seats.aero/reference
    params = [
        ("origin", origin),
        ("destination", destination),
        ("startDate", departure_date),
        ("endDate", departure_date),
    ]
    qs = "&".join(f"{k}={v}" for k, v in params)
    url = f"{BASE_URL}/search?{qs}"

    req = urllib.request.Request(url, method="GET")
    req.add_header("Partner-Authorization", key)
    req.add_header("Accept", "application/json")

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read().decode("utf-8")
            data = json.loads(body)
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8") if e.fp else ""
        return {
            "american": {"source": "seats.aero", "points": None, "error": f"seats.aero API error {e.code}: {err_body[:200]}"},
            "united": {"source": "seats.aero", "points": None, "error": f"seats.aero API error {e.code}"},
            "delta": {"source": "seats.aero", "points": None, "error": f"seats.aero API error {e.code}"},
        }
    except (urllib.error.URLError, json.JSONDecodeError, OSError) as e:
        return {
            "american": {"source": "seats.aero", "points": None, "error": str(e)},
            "united": {"source": "seats.aero", "points": None, "error": str(e)},
            "delta": {"source": "seats.aero", "points": None, "error": str(e)},
        }

    by_provider = _extract_miles_from_response(data)
    results = {}
    for pid in ("american", "united", "delta"):
        if by_provider.get(pid):
            results[pid] = {"source": "seats.aero", "points": by_provider[pid], "error": None}
        else:
            results[pid] = {"source": "seats.aero", "points": None, "error": "No availability in cached data for this route/date."}
    return results
