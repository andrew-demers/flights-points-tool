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
        try:
            browser = p.chromium.launch(
                channel="chrome",
                headless=False,
                args=["--disable-blink-features=AutomationControlled"],
            )
        except Exception:
            browser = p.chromium.launch(
                headless=False,
                args=["--disable-blink-features=AutomationControlled"],
            )
        context = browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        )
        # Remove navigator.webdriver property that triggers bot detection
        context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        page = context.new_page()
        page.goto("https://seats.aero/login", wait_until="domcontentloaded")

        print("Once logged in, press Enter here to save the session.")
        print("(Or wait — auto-detection will save it within 3 minutes)")
        print()

        import threading
        save_now = threading.Event()
        def _wait_for_enter():
            input()
            save_now.set()
        t = threading.Thread(target=_wait_for_enter, daemon=True)
        t.start()

        deadline = time.time() + 180
        while time.time() < deadline:
            if save_now.is_set():
                break
            url = page.url
            if "seats.aero" in url and "accounts.google.com" not in url and "login" not in url:
                break
            time.sleep(1)

        print("Saving session...")
        session_path.parent.mkdir(parents=True, exist_ok=True)
        storage = context.storage_state()
        session_path.write_text(json.dumps(storage, indent=2))
        browser.close()

    print(f"Session saved to {session_path}")
    print("The flights-points MCP will now use this session for live award searches.")


if __name__ == "__main__":
    setup_seats_aero_session()
