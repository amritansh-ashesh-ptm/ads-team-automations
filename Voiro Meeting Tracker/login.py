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
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(config.REPORTS_URL)

        print("\n>> Click 'Continue with Google' and sign in.")
        print(">> Waiting for you to reach the reports page (not the login page)...")
        time.sleep(4)  # let the initial client-side redirect to /login settle first
        deadline = time.time() + TIMEOUT_S
        while time.time() < deadline:
            url = page.url
            if "/phoenix/reports" in url and "login" not in url:
                time.sleep(2)  # let cookies settle
                print(">> Detected reports page. Session saved.")
                ctx.close()
                return
            time.sleep(1)
        print(">> Timed out waiting for reports page. Re-run login.py.")
        ctx.close()


if __name__ == "__main__":
    main()
