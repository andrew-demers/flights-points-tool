"""
American Airlines AAdvantage award miles lookup via aa.com.

Uses Playwright to run an award search and parse miles from results.
Optional: install with pip install flights-points-tool[scrape] and run
playwright install chromium. Set FLIGHTS_POINTS_DISABLE_AA_SCRAPE=1 to disable.
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
    Run an award search on aa.com for the given route and date; return list of miles required.
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
    # departure_date YYYY-MM-DD
    if len(departure_date) != 10 or departure_date[4] != "-" or departure_date[7] != "-":
        return None

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.set_default_timeout(25_000)
            page.goto(
                "https://www.aa.com/booking/find-flights?tripType=oneWay&awardBooking=true",
                wait_until="domcontentloaded",
            )
            # Cookie/modal dismiss if present
            try:
                page.get_by_role("button", name=re.compile(r"accept|agree|continue", re.I)).first.click(timeout=3000)
            except Exception:
                pass

            # Origin: try common patterns (aa.com uses various inputs)
            try:
                orig_input = page.locator('input[name="origin"], input[id*="origin"], [data-test-id="origin"]').first
                orig_input.fill(origin)
            except Exception:
                try:
                    page.get_by_placeholder("From").fill(origin)
                except Exception:
                    pass

            # Destination
            try:
                dest_input = page.locator('input[name="destination"], input[id*="destination"], [data-test-id="destination"]').first
                dest_input.fill(destination)
            except Exception:
                try:
                    page.get_by_placeholder("To").fill(destination)
                except Exception:
                    pass

            # Date: often a single date input or day/month
            try:
                date_input = page.locator('input[name*="date"], input[id*="date"], [data-test-id*="date"]').first
                date_input.fill(departure_date)
            except Exception:
                pass

            # Search
            try:
                page.get_by_role("button", name=re.compile(r"search|find", re.I)).first.click(timeout=5000)
            except Exception:
                try:
                    page.locator('button[type="submit"]').first.click(timeout=5000)
                except Exception:
                    browser.close()
                    return None

            page.wait_for_load_state("networkidle", timeout=15_000)

            # Collect all visible text and extract numbers that look like miles (e.g. 7,500 or 12500)
            content = page.content()
            # Common pattern: "12,500" or "12500" near "miles" or "AAdvantage"
            miles_pattern = re.compile(r"(?:miles|AAdvantage|miles required)[:\s]*([0-9,]+)|([0-9,]{2,6})\s*(?:miles|k)", re.I)
            found = set()
            for m in miles_pattern.finditer(content):
                for g in m.groups():
                    if g:
                        num = int(g.replace(",", ""))
                        if 2_000 <= num <= 500_000:  # sane award range
                            found.add(num)
            # Also standalone numbers in result cards (e.g. 12500)
            standalone = re.findall(r">\s*([0-9]{1,3}(?:,[0-9]{3})*)\s*<", content)
            for s in standalone:
                num = int(s.replace(",", ""))
                if 2_000 <= num <= 500_000:
                    found.add(num)

            browser.close()
            if not found:
                return None
            return {
                "source": "aa.com",
                "points": sorted(found),
                "error": None,
            }
        except Exception:
            try:
                browser.close()
            except Exception:
                pass
            return None
