"""
seats.aero browser scraper using Playwright headed mode.

Saves your seats.aero session (cookies) after first login so subsequent runs
don't require interaction. Session stored at ~/.config/flights-points/seats_aero_session.json
or the path in SEATS_AERO_SESSION_FILE.

First run: opens a browser window for you to log in to seats.aero, then saves the session.
Subsequent runs: loads the saved session and searches directly.

Set FLIGHTS_POINTS_HEADLESS=1 to disable headed mode (breaks this scraper if not logged in).
"""

from __future__ import annotations

import json
import os
import pathlib
import re
import time
from typing import Any

_DEFAULT_SESSION_FILE = pathlib.Path.home() / ".config" / "flights-points" / "seats_aero_session.json"

PROGRAM_PATTERNS = {
    "american": re.compile(r"american|aadvantage|aa\b", re.I),
    "united": re.compile(r"united|mileageplus|ua\b", re.I),
    "delta": re.compile(r"delta|skymiles|dl\b", re.I),
}


def _session_file() -> pathlib.Path:
    custom = os.environ.get("SEATS_AERO_SESSION_FILE", "").strip()
    return pathlib.Path(custom) if custom else _DEFAULT_SESSION_FILE


def _save_session(context, path: pathlib.Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    storage = context.storage_state()
    path.write_text(json.dumps(storage, indent=2))


def _load_session(context, path: pathlib.Path) -> bool:
    if not path.exists():
        return False
    try:
        state = json.loads(path.read_text())
        context.add_cookies(state.get("cookies", []))
        return True
    except Exception:
        return False


def _check_logged_in(page) -> bool:
    try:
        content = page.content().lower()
        # Logged in if we see profile/account/logout, but not a login form
        has_auth_wall = "sign in" in content and "password" in content
        return not has_auth_wall
    except Exception:
        return False


def _wait_for_login(page) -> None:
    """Block until user completes login (URL leaves /login or /signin)."""
    print("[seats.aero] Please log in to seats.aero in the browser window that opened.")
    print("[seats.aero] The search will continue automatically once you are logged in.")
    deadline = time.time() + 180  # 3-minute timeout
    while time.time() < deadline:
        url = page.url
        if "login" not in url and "signin" not in url and "seats.aero" in url:
            content = page.content().lower()
            if "sign in" not in content or "password" not in content:
                print("[seats.aero] Login detected, continuing...")
                return
        time.sleep(2)
    raise TimeoutError("Timed out waiting for seats.aero login (3 min limit).")


def _extract_awards_from_page(page) -> dict[str, list[int]]:
    """
    Parse seats.aero search results. Returns { program_id -> sorted list of mile costs }.
    seats.aero shows results grouped by program with mile costs next to availability.
    """
    results: dict[str, list[int]] = {}

    try:
        # Wait briefly for dynamic content to settle
        page.wait_for_load_state("networkidle", timeout=20_000)
    except Exception:
        pass

    content = page.content()

    # Strategy: find sections associated with each program name and extract nearby numbers.
    # seats.aero renders availability cards with program name + mile cost (e.g. "12,500 miles").
    mile_num = re.compile(r"([0-9]{1,3}(?:,[0-9]{3})+|[0-9]{4,6})")

    # Split content into ~500-char chunks anchored around program name mentions
    # and extract numbers in the 2k-500k range from each chunk.
    for pid, pattern in PROGRAM_PATTERNS.items():
        found: set[int] = set()
        for m in pattern.finditer(content):
            start = max(0, m.start() - 300)
            end = min(len(content), m.end() + 300)
            chunk = content[start:end]
            for nm in mile_num.finditer(chunk):
                try:
                    val = int(nm.group().replace(",", ""))
                    if 2_000 <= val <= 500_000:
                        found.add(val)
                except ValueError:
                    pass
        if found:
            results[pid] = sorted(found)

    return results


def fetch_from_seats_aero_browser(
    origin: str,
    destination: str,
    departure_date: str,
) -> dict[str, dict[str, Any]]:
    """
    Open seats.aero in a headed browser and return live award availability.

    On first call: prompts user to log in; saves session for future calls.
    Returns { "american": { "source": ..., "points": [...], "error": ... }, ... }.
    Empty dict if Playwright not installed.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {}

    origin = origin.strip().upper()
    destination = destination.strip().upper()
    if len(origin) != 3 or len(destination) != 3:
        return {}
    if len(departure_date) != 10:
        return {}

    headless = os.environ.get("FLIGHTS_POINTS_HEADLESS", "").lower() in ("1", "true", "yes")
    session_path = _session_file()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless, slow_mo=80)
        context = browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        )

        loaded = _load_session(context, session_path)
        page = context.new_page()

        try:
            # Navigate to seats.aero and check login state
            page.goto("https://seats.aero", wait_until="domcontentloaded", timeout=20_000)

            if not loaded or not _check_logged_in(page):
                # Need fresh login
                page.goto("https://seats.aero/login", wait_until="domcontentloaded", timeout=15_000)
                _wait_for_login(page)
                _save_session(context, session_path)

            # Navigate to search - try URL params first
            search_url = (
                f"https://seats.aero/search"
                f"?origin_airport={origin}&destination_airport={destination}"
                f"&start_date={departure_date}&end_date={departure_date}"
            )
            page.goto(search_url, wait_until="domcontentloaded", timeout=20_000)

            # If that didn't load results, try the simpler param format
            time.sleep(2)
            if not any(p.search(page.content()) for p in PROGRAM_PATTERNS.values()):
                search_url2 = (
                    f"https://seats.aero/search"
                    f"?origin={origin}&destination={destination}&date={departure_date}"
                )
                page.goto(search_url2, wait_until="domcontentloaded", timeout=20_000)
                time.sleep(2)

            # If still no program names visible, try filling the form
            if not any(p.search(page.content()) for p in PROGRAM_PATTERNS.values()):
                page.goto("https://seats.aero/search", wait_until="domcontentloaded", timeout=15_000)
                try:
                    page.get_by_placeholder(re.compile(r"origin|from", re.I)).first.fill(origin)
                    page.get_by_placeholder(re.compile(r"destination|to", re.I)).first.fill(destination)
                    page.get_by_role("button", name=re.compile(r"search|find", re.I)).first.click(timeout=5_000)
                except Exception:
                    pass
                time.sleep(3)

            awards = _extract_awards_from_page(page)

            # Refresh session after successful search
            _save_session(context, session_path)
            browser.close()

        except Exception as e:
            try:
                browser.close()
            except Exception:
                pass
            err = str(e)
            return {pid: {"source": "seats.aero (browser)", "points": None, "error": err}
                    for pid in ("american", "united", "delta")}

    out: dict[str, dict[str, Any]] = {}
    for pid in ("american", "united", "delta"):
        if awards.get(pid):
            out[pid] = {"source": "seats.aero (browser)", "points": awards[pid], "error": None}
        else:
            out[pid] = {"source": "seats.aero (browser)", "points": None, "error": "No availability found."}
    return out
