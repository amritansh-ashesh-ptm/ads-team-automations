"""Open the reports page with the saved session and capture what's there,
to confirm login persisted and to see the layout.

    .venv/bin/python inspect_page.py
"""
from playwright.sync_api import sync_playwright

import config


def main():
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=str(config.PROFILE_DIR),
            channel="chrome",
            headless=True,
            accept_downloads=True,
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(config.REPORTS_URL, wait_until="networkidle")
        print("FINAL URL:", page.url)
        print("TITLE   :", page.title())
        logged_in = "phoenix/reports" in page.url and "google" not in page.url.lower()
        print("LOGGED IN:", logged_in)
        shot = config.BASE / "reports_page.png"
        page.screenshot(path=str(shot), full_page=True)
        print("SCREENSHOT:", shot)
        ctx.close()


if __name__ == "__main__":
    main()
