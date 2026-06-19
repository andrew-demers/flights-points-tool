"""
One-time setup: log in to seats.aero in a browser and save the session.

Run once:
    uv run python -m flights_points.setup_login

After this, the flights-points MCP will automatically use the saved session
for live award searches on routes not in the seats.aero cached data.
"""

from __future__ import annotations

import json
import pathlib
import sys
import time

_SESSION_FILE = pathlib.Path.home() / ".config" / "flights-points" / "seats_aero_session.json"


def setup_seats_aero_session(session_path: pathlib.Path = _SESSION_FILE) -> None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Playwright is not installed. Run: uv pip install playwright && uv run playwright install chromium")
        sys.exit(1)

    print("Opening seats.aero in a browser window.")
    print("Please log in, then close the browser OR wait — the session saves automatically after login.")
    print()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=50)
        context = browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()
        page.goto("https://seats.aero/login", wait_until="domcontentloaded")

        print("Waiting for you to log in... (3 minute timeout)")
        deadline = time.time() + 180
        logged_in = False
        while time.time() < deadline:
            url = page.url
            if "seats.aero" in url and "login" not in url and "signin" not in url:
                content = page.content().lower()
                if "sign in" not in content or "password" not in content:
                    logged_in = True
                    break
            time.sleep(2)

        if not logged_in:
            print("Timed out waiting for login.")
            browser.close()
            sys.exit(1)

        print("Login detected! Saving session...")
        session_path.parent.mkdir(parents=True, exist_ok=True)
        storage = context.storage_state()
        session_path.write_text(json.dumps(storage, indent=2))
        browser.close()

    print(f"Session saved to {session_path}")
    print("The flights-points MCP will now use this session for live award searches.")


if __name__ == "__main__":
    setup_seats_aero_session()
