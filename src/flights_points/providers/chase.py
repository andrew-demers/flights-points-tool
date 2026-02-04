"""
Chase Ultimate Rewards points lookup via Chase Travel portal.

The Chase Travel portal is powered by Expedia and typically requires sign-in.
This module attempts a public search when possible; otherwise returns a clear
message that sign-in is required. Install flights-points-tool[scrape] and
playwright install chromium. Set FLIGHTS_POINTS_DISABLE_CHASE_SCRAPE=1 to disable.
"""

from __future__ import annotations

import re
from typing import Any


def _parse_points_from_content(content: str) -> set[int]:
    """Extract numbers that look like points (1k–500k) from Chase/Expedia portal."""
    found = set()
    # "12,500 points" or "points" near number
    points_pattern = re.compile(
        r"(?:points|Ultimate Rewards)[:\s]*([0-9,]+)|([0-9,]{2,6})\s*(?:points|pts)",
        re.I,
    )
    for m in points_pattern.finditer(content):
        for g in m.groups():
            if g:
                num = int(g.replace(",", ""))
                if 1_000 <= num <= 500_000:
                    found.add(num)
    for m in re.findall(r">\s*([0-9]{1,3}(?:,[0-9]{3})*)\s*<", content):
        num = int(m.replace(",", ""))
        if 1_000 <= num <= 500_000:
            found.add(num)
    return found


def fetch_award_points(
    origin: str,
    destination: str,
    departure_date: str,
    adults: int = 1,
) -> dict[str, Any] | None:
    """
    Attempt to run a flight search on Chase Travel and parse points required.
    Chase Travel often requires sign-in; if the page redirects to login or shows
    no results, returns a dict with error message. Returns None only on
    Playwright import or unexpected failure.
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
    # Many US sites use MM/DD/YYYY
    month, day, year = departure_date[5:7], departure_date[8:10], departure_date[:4]
    date_us = f"{month}/{day}/{year}"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.set_default_timeout(20_000)
            # Chase Travel - may redirect to login or show Expedia-powered search
            page.goto(
                "https://www.chase.com/travel",
                wait_until="domcontentloaded",
            )
            # Accept cookies if shown
            try:
                page.get_by_role("button", name=re.compile(r"accept|agree|continue", re.I)).first.click(timeout=3000)
            except Exception:
                pass

            # Check if we're on a login or gate page
            content_lower = page.content().lower()
            if "sign in" in content_lower and "flight" not in content_lower[:5000]:
                browser.close()
                return {
                    "source": "chase.com",
                    "points": None,
                    "error": "Chase Travel requires sign-in; real lookup unavailable.",
                }

            # Try to find flight search: From, To, Date
            try:
                page.get_by_placeholder("From").fill(origin)
            except Exception:
                try:
                    page.locator('input[aria-label*="From"], input[name*="origin"], input[id*="origin"]').first.fill(origin)
                except Exception:
                    pass

            try:
                page.get_by_placeholder("To").fill(destination)
            except Exception:
                try:
                    page.locator('input[aria-label*="To"], input[name*="destination"], input[id*="destination"]').first.fill(destination)
                except Exception:
                    pass

            try:
                page.locator('input[placeholder*="date"], input[aria-label*="date"], input[name*="date"]').first.fill(date_us)
            except Exception:
                pass

            try:
                page.get_by_role("button", name=re.compile(r"search|find", re.I)).first.click(timeout=5000)
            except Exception:
                try:
                    page.locator('button[type="submit"]').first.click(timeout=5000)
                except Exception:
                    browser.close()
                    return {
                        "source": "chase.com",
                        "points": None,
                        "error": "Chase Travel requires sign-in; real lookup unavailable.",
                    }

            page.wait_for_load_state("networkidle", timeout=15_000)
            content = page.content()
            # If we see sign-in again after search, we were gated
            if "sign in" in content.lower() and "points" not in content.lower():
                browser.close()
                return {
                    "source": "chase.com",
                    "points": None,
                    "error": "Chase Travel requires sign-in; real lookup unavailable.",
                }

            found = _parse_points_from_content(content)
            browser.close()

            if not found:
                return {
                    "source": "chase.com",
                    "points": None,
                    "error": "No points results (Chase Travel may require sign-in).",
                }
            return {
                "source": "chase.com/travel",
                "points": sorted(found),
                "error": None,
            }
        except Exception as e:
            try:
                browser.close()
            except Exception:
                pass
            return {
                "source": "chase.com",
                "points": None,
                "error": f"Chase Travel lookup failed: {e!s}",
            }
