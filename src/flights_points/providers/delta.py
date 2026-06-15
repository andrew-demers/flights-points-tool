"""
Delta Air Lines SkyMiles award lookup via delta.com.

Uses Playwright to run an award search and parse miles from results.
Optional: install with pip install flights-points-tool[scrape] and run
playwright install chromium. Set FLIGHTS_POINTS_DISABLE_DELTA_SCRAPE=1 to disable.
"""

from __future__ import annotations

import re
from typing import Any


def fetch_award_miles(
    origin: str,
    destination: str,
    departure_date: str,
    adults: int = 1,
) -> dict[str, Any] | None:
    """
    Run an award search on delta.com for the given route and date; return list of miles required.
    Returns None if Playwright is not installed, or on any scrape/parse failure.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return None

    origin = origin.strip().upper()
    destination = destination.strip().upper()
    if len(origin) != 3 or len(destination) != 3:
        return None
    if len(departure_date) != 10 or departure_date[4] != "-" or departure_date[7] != "-":
        return None

    # delta.com uses YYYY-MM-DD in the URL directly
    url = (
        f"https://www.delta.com/us/en/flight-search/book-a-flight"
        f"?tripType=ONE_WAY&fromAirportCode={origin}&toAirportCode={destination}"
        f"&departureDate={departure_date}&paxCount={adults}&awardTravel=true"
    )

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.set_default_timeout(30_000)
            page.goto(url, wait_until="domcontentloaded")

            # Dismiss cookie/modal if present
            try:
                page.get_by_role("button", name=re.compile(r"accept|agree|continue|close", re.I)).first.click(timeout=3000)
            except Exception:
                pass

            page.wait_for_load_state("networkidle", timeout=20_000)

            content = page.content()
            browser.close()

            # Match patterns like "12,500" or "12500" near "miles" or "SkyMiles"
            miles_pattern = re.compile(
                r"(?:miles|SkyMiles|skymiles)[:\s]*([0-9,]+)|([0-9,]{2,6})\s*(?:miles|SkyMiles)",
                re.I,
            )
            found = set()
            for m in miles_pattern.finditer(content):
                for g in m.groups():
                    if g:
                        num = int(g.replace(",", ""))
                        if 2_000 <= num <= 500_000:
                            found.add(num)

            # Standalone numbers in result cards
            standalone = re.findall(r">\s*([0-9]{1,3}(?:,[0-9]{3})*)\s*<", content)
            for s in standalone:
                num = int(s.replace(",", ""))
                if 2_000 <= num <= 500_000:
                    found.add(num)

            if not found:
                return None
            return {
                "source": "delta.com",
                "points": sorted(found),
                "error": None,
            }
        except Exception:
            try:
                browser.close()
            except Exception:
                pass
            return None
