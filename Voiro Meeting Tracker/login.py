"""One-time login. Run this, sign in with Google in the window that opens, and
navigate until the reports page is showing. The script watches the browser and
saves the session automatically once you land on the reports page.

    .venv/bin/python login.py
"""
import time

from playwright.sync_api import sync_playwright

import config

TIMEOUT_S = 300  # 5 min for you to click through Google


def main():
    config.PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=str(config.PROFILE_DIR),
            channel="chrome",
            headless=False,
            accept_downloads=True,
            # Pin the viewport so the headed login session renders the same
            # responsive layout as the headless runs (generate_meeting_report.py,
            # inspect_page.py) — a headed window's actual OS size can otherwise
            # differ and collapse the sidebar into a layout without this marker.
            viewport={"width": 1280, "height": 800},
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(config.REPORTS_URL)

        print("\n>> Click 'Continue with Google' and sign in.")
        print(">> Waiting for you to reach the reports page (not the login page)...")
        # Check real page content, not the URL: the SPA shows the /phoenix/reports
        # URL for a few seconds while it bootstraps even when NOT logged in, before
        # its JS checks the session and redirects to /login. A URL (or URL-timing)
        # check can't tell bootstrap-in-progress from actually-authenticated —
        # only the presence of authenticated-only DOM content can.
        report_pane_toggle = page.locator("a.cursor.ps-4")
        deadline = time.time() + TIMEOUT_S
        while time.time() < deadline:
            if "/login" not in page.url and report_pane_toggle.count() > 0:
                print(">> Detected reports page. Session saved.")
                ctx.close()
                return
            time.sleep(1)
        print(">> Timed out waiting for reports page. Re-run login.py.")
        ctx.close()


if __name__ == "__main__":
    main()
