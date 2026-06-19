"""
United MileagePlus award miles lookup via united.com.

Uses Playwright to run an award search and parse miles from results.
Optional: install with pip install flights-points-tool[scrape] and run
playwright install chromium. Set FLIGHTS_POINTS_DISABLE_UNITED_SCRAPE=1 to disable.
"""

from __future__ import annotations

import os
import re
from typing import Any


def _parse_miles_from_content(content: str) -> set[int]:
    """Extract numbers that look like award miles (2k–500k) from page HTML/text."""
    found = set()
    # "12,500 miles" or "12500 miles" or "MileagePlus" near number
    miles_pattern = re.compile(
        r"(?:miles|MileagePlus|miles required|saver)[:\s]*([0-9,]+)|([0-9,]{2,6})\s*(?:miles|k)",
        re.I,
    )
    for m in miles_pattern.finditer(content):
        for g in m.groups():
            if g:
                num = int(g.replace(",", ""))
                if 2_000 <= num <= 500_000:
                    found.add(num)
    # Standalone numbers in result cards
    for m in re.findall(r">\s*([0-9]{1,3}(?:,[0-9]{3})*)\s*<", content):
        num = int(m.replace(",", ""))
        if 2_000 <= num <= 500_000:
            found.add(num)
    return found


def fetch_award_miles(
    origin: str,
    destination: str,
    departure_date: str,
    adults: int = 1,
) -> dict[str, Any] | None:
    """
    Run an award search on united.com for the given route and date; return list of miles required.
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
    # United often uses MM/DD/YYYY in the date field
    month, day, year = departure_date[5:7], departure_date[8:10], departure_date[:4]
    date_us = f"{month}/{day}/{year}"

    headless = os.environ.get("FLIGHTS_POINTS_HEADLESS", "").lower() in ("1", "true", "yes")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless, slow_mo=80)
        try:
            page = browser.new_page()
            page.set_default_timeout(25_000)
            page.goto(
                "https://www.united.com/en/us/book-flight/united-award-travel",
                wait_until="domcontentloaded",
            )
            # Dismiss cookie/modal if present
            try:
                page.get_by_role("button", name=re.compile(r"accept|agree|continue|ok", re.I)).first.click(timeout=3000)
            except Exception:
                pass

            # Ensure "Miles" is selected for price display (United shows Money | Miles)
            try:
                page.get_by_text("Miles", exact=False).first.click(timeout=3000)
            except Exception:
                pass

            # One-way
            try:
                page.get_by_role("link", name=re.compile(r"one-way|one way", re.I)).first.click(timeout=3000)
            except Exception:
                pass

            # From (origin)
            try:
                page.get_by_placeholder("From").fill(origin)
            except Exception:
                try:
                    page.locator('input[aria-label*="From"], input[name*="origin"]').first.fill(origin)
                except Exception:
                    pass

            # To (destination)
            try:
                page.get_by_placeholder("To").fill(destination)
            except Exception:
                try:
                    page.locator('input[aria-label*="To"], input[name*="destination"]').first.fill(destination)
                except Exception:
                    pass

            # Date: United uses "month/day/year"
            try:
                page.locator('input[placeholder*="date"], input[aria-label*="date"], input[name*="date"]').first.fill(date_us)
            except Exception:
                pass

            # Find flights
            try:
                page.get_by_role("button", name=re.compile(r"find flights|search", re.I)).first.click(timeout=5000)
            except Exception:
                try:
                    page.locator('button[type="submit"]').first.click(timeout=5000)
                except Exception:
                    browser.close()
                    return None

            page.wait_for_load_state("networkidle", timeout=18_000)
            content = page.content()
            found = _parse_miles_from_content(content)
            browser.close()

            if not found:
                return None
            return {
                "source": "united.com",
                "points": sorted(found),
                "error": None,
            }
        except Exception:
            try:
                browser.close()
            except Exception:
                pass
            return None
