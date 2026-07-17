"""Create a Meeting Report and download it once we can PROVE it's the one we
just made — not just whatever happens to be on top.

Selector strategy (in order of trust):
  1. Stable `id` attributes on the form's own <input> elements (#reportType,
     #dateRange, #name, #sales_person_id, #include_org). These are the
     single most durable hook available — authored by the app, not derived
     from styling, and unlikely to change on a visual redesign.
  2. Visible TEXT (option labels, button text) — content, not styling.
  3. The date-range popup is scoped to its own real component element,
     <bs-daterangepicker-container> (ngx-bootstrap's library element, not a
     style-derived class), appended directly to <body> — structurally
     separate from the report table and side panel, so queries inside it
     can never accidentally match background page content.
  4. Pixel position — only for the couple of icon-only buttons with no id,
     text, or aria hook at all (the '+'/zig-zag toggles). Most fragile;
     flagged inline. Never used against anything outside the open pane/modal.

Freshness guard: after clicking Generate, we read the exact report name the
form showed us (from #name) *before* submitting. We poll Report History for
a row whose text contains that exact name AND whose status is "Ready" AND
whose time-label is exactly "now". If the deadline passes without that
combination, we raise instead of downloading whatever is on top — a
silently-failed Generate must not result in silently-stale data, and we
never fall back to "just grab the top row" without that proof.

    .venv/bin/python generate_meeting_report.py
"""
import datetime
import re
import time

import config
from playwright.sync_api import sync_playwright

REPORT_TYPE = "Meeting Report"  # one of: Billing/Meeting/Pacing/Pipeline/Tickets Report
SALESPERSON = config.SALESPERSON
START_DATE = config.START_DATE
END_DATE = config.END_DATE

POLL_TIMEOUT_S = 180  # report generation can be slow under load — don't rush this
POLL_INTERVAL_S = 1.5

# Generous ceiling for every Playwright action (click/fill/goto/download) —
# the site can be slow or briefly overloaded; a fast default timeout would
# misread "still loading" as "broken". Retrying the whole flow (below) is the
# real safety net, not a short per-action timeout.
DEFAULT_ACTION_TIMEOUT_MS = 60_000
PAGE_LOAD_TIMEOUT_MS = 60_000
DOWNLOAD_TIMEOUT_MS = 60_000

MAX_ATTEMPTS = 3
RETRY_BACKOFF_S = 5


class ManualLoginRequired(RuntimeError):
    """The Google session itself needs a human to run login.py — retrying
    just means more automated hits against Google's login, which is what
    risks getting flagged in the first place. Not retryable."""

# The date-range popup is a single <bs-daterangepicker-container> appended
# directly to <body> — see module docstring point 3.
_CAL_SCOPE_JS = "document.querySelector('bs-daterangepicker-container')"


def open_report_pane(page):
    # Fragile: no id/text/aria hook on this icon-only toggle. Positional fallback.
    page.locator("a.cursor.ps-4").first.click()
    page.wait_for_timeout(800)


def select_report_type(page, report_type):
    page.locator("#reportType").click()
    page.wait_for_timeout(500)
    page.get_by_text(report_type, exact=True).click()
    page.wait_for_timeout(1200)


def _drill_start_day(page, target_date):
    """Left (start) pane: click currently-shown year -> target year -> target
    month -> target day. Everything scoped inside the calendar container."""
    year_labels = page.evaluate(
        f"""() => Array.from({_CAL_SCOPE_JS}.querySelectorAll('*'))
            .filter(e => e.children.length===0 && /^\\d{{4}}$/.test(e.textContent.trim()))
            .map(e => {{ const r=e.getBoundingClientRect(); return {{x:r.x,y:r.y,w:r.width,h:r.height}}; }})
            .sort((a,b)=>a.x-b.x)"""
    )
    if len(year_labels) < 2:
        raise RuntimeError(f"Expected 2 year labels (start/end) inside the calendar, found {len(year_labels)}")
    yl = year_labels[0]  # left = start pane
    page.mouse.click(yl["x"] + yl["w"] / 2, yl["y"] + yl["h"] / 2)
    page.wait_for_timeout(600)

    year_cells = page.evaluate(
        f"""() => Array.from({_CAL_SCOPE_JS}.querySelectorAll('*'))
            .filter(e => e.children.length===0 && e.textContent.trim()==='{target_date.year}')
            .map(e => {{ const r=e.getBoundingClientRect(); return {{x:r.x,y:r.y,w:r.width,h:r.height}}; }})"""
    )
    if not year_cells:
        raise RuntimeError(f"Target year {target_date.year} not visible in the year grid (out of range?)")
    yc = year_cells[0]
    page.mouse.click(yc["x"] + yc["w"] / 2, yc["y"] + yc["h"] / 2)
    page.wait_for_timeout(600)

    month_name = target_date.strftime("%B")
    month_cells = page.evaluate(
        f"""() => Array.from({_CAL_SCOPE_JS}.querySelectorAll('*'))
            .filter(e => e.children.length===0 && e.textContent.trim()==='{month_name}')
            .map(e => {{ const r=e.getBoundingClientRect(); return {{x:r.x,y:r.y,w:r.width,h:r.height}}; }})
            .sort((a,b)=>a.x-b.x)"""
    )
    if len(month_cells) < 2:
        raise RuntimeError(f"Expected 2 '{month_name}' cells, found {len(month_cells)}")
    mc = month_cells[0]
    page.mouse.click(mc["x"] + mc["w"] / 2, mc["y"] + mc["h"] / 2)
    page.wait_for_timeout(600)

    day_str = str(target_date.day)
    day_cells = page.evaluate(
        f"""() => Array.from({_CAL_SCOPE_JS}.querySelectorAll('*'))
            .filter(e => e.children.length===0 && e.textContent.trim()==='{day_str}' && !e.className.includes('is-other-month'))
            .map(e => {{ const r=e.getBoundingClientRect(); return {{x:r.x,y:r.y,w:r.width,h:r.height}}; }})
            .sort((a,b)=>a.x-b.x)"""
    )
    if len(day_cells) < 2:
        raise RuntimeError(f"Expected 2 in-month day-{day_str} cells, found {len(day_cells)}")
    dc = day_cells[0]  # left = start pane
    page.mouse.click(dc["x"] + dc["w"] / 2, dc["y"] + dc["h"] / 2)
    page.wait_for_timeout(600)


def set_date_range(page, start_date, end_date):
    page.locator("#dateRange").click()
    page.wait_for_timeout(800)
    _drill_start_day(page, start_date)

    # ponytail: after the start-pane drills to its day grid, the end-pane
    # snaps back to day-view too, showing whatever it was already on (the
    # picker's own default, e.g. "This Month"). We only click its day
    # directly rather than re-drilling year/month for it — verified to work
    # when end_date falls inside that already-shown month (true for
    # "today", since the default range always includes today). If a caller
    # ever needs an end_date outside the default month, this needs a real
    # year->month->day drill for the end pane added back in — untested for
    # that case.
    day_str = str(end_date.day)
    day_cells = page.evaluate(
        f"""() => Array.from({_CAL_SCOPE_JS}.querySelectorAll('*'))
            .filter(e => e.children.length===0 && e.textContent.trim()==='{day_str}' && !e.className.includes('is-other-month'))
            .map(e => {{ const r=e.getBoundingClientRect(); return {{x:r.x,y:r.y,w:r.width,h:r.height}}; }})
            .sort((a,b)=>a.x-b.x)"""
    )
    if len(day_cells) < 2:
        raise RuntimeError(
            f"Expected end-pane day '{day_str}' already visible without redrilling "
            f"(found {len(day_cells)} candidates) — end_date is outside the default "
            "displayed month; a real drill for the end pane needs implementing for this case."
        )
    dc = day_cells[-1]  # right = end pane
    page.mouse.click(dc["x"] + dc["w"] / 2, dc["y"] + dc["h"] / 2)
    page.wait_for_timeout(600)


def read_report_name(page):
    return page.locator("#name").input_value()


def set_salesperson(page, name):
    page.locator("#sales_person_id").click()
    page.wait_for_timeout(600)
    page.get_by_placeholder("Search", exact=False).first.fill(name)
    page.wait_for_timeout(800)
    page.get_by_text(name, exact=False).first.click()
    page.wait_for_timeout(500)


def ensure_include_org_yes(page):
    checkbox = page.locator("#include_org")
    if not checkbox.is_checked():
        checkbox.click()
        page.wait_for_timeout(300)
    assert checkbox.is_checked(), "Include Org checkbox did not end up checked"


def click_generate(page):
    page.get_by_text("Generate Report", exact=True).last.click()
    page.wait_for_timeout(1000)


def wait_for_fresh_ready_row(page, report_type, expected_name, timeout_s=POLL_TIMEOUT_S):
    """Poll Report History for a row matching our exact report name, Ready,
    and time-labeled 'now'. Tolerates transient empty reads (the list has
    been observed to blip empty for a few seconds, presumably a re-render).
    Raises on timeout rather than falling back to 'whatever is on top' —
    a report we can't positively identify as fresh must not be downloaded."""
    deadline = time.time() + timeout_s
    last_seen = None
    while time.time() < deadline:
        rows = page.locator("li").filter(has_text=report_type)
        for i in range(rows.count()):
            text = rows.nth(i).inner_text().replace("\n", " | ")
            if expected_name in text:
                last_seen = text
                is_ready = "Ready" in text
                is_now = bool(re.search(r"\bnow\b", text, re.IGNORECASE))
                if is_ready and is_now:
                    return rows.nth(i)
                break  # found our row but not ready/now yet — keep polling
        page.wait_for_timeout(int(POLL_INTERVAL_S * 1000))
    raise RuntimeError(
        f"Timed out after {timeout_s}s waiting for a fresh Ready row named "
        f"'{expected_name}'. Last matching row seen: {last_seen!r}. "
        "Refusing to fall back to 'topmost row' — it could be stale."
    )


def download_row(page, row):
    row.hover()
    page.wait_for_timeout(400)
    config.DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    # The actual file can take a while to start streaming under load —
    # give it real room rather than the 30s default.
    with page.expect_download(timeout=DOWNLOAD_TIMEOUT_MS) as dl_info:
        row.locator(".icon2-download").click()
    download = dl_info.value
    dest = config.DOWNLOAD_DIR / f"meeting_report_{datetime.datetime.now():%Y%m%d_%H%M%S}.xlsx"
    download.save_as(str(dest))
    print("Suggested filename from site (arbitrary, ignored):", download.suggested_filename)
    print("Saved to:", dest)
    return dest


def ensure_logged_in(page):
    """Google periodically requires re-confirming the OAuth grant (no
    password/2FA, just re-picking the account) even while the underlying
    Google session is still valid — this handles that click-through. If a
    real email/password prompt shows up instead, the Google session itself
    has expired and this raises instead of guessing at credentials."""
    if "login" not in page.url:
        return

    page.get_by_text("Continue with Google").click(timeout=DEFAULT_ACTION_TIMEOUT_MS)

    try:
        page.get_by_text(config.GOOGLE_ACCOUNT_EMAIL).click(timeout=10_000)
    except Exception:
        raise ManualLoginRequired(
            "Google account chooser didn't appear (full email/password/2FA "
            "prompt instead) — the Google session itself expired. Run login.py."
        )

    # The click above can also "succeed" (no exception) but land somewhere
    # other than the consent screen — observed variants: Google's identifier
    # (type-your-email) page when the account's underlying session expired,
    # and a "/signin/rejected" page when Google's anomaly detection balks at
    # the automated sign-in itself. Catch both here instead of falling through
    # to the Continue/Allow probe (which times out) and a misleading generic
    # error. (.click() doesn't wait for the resulting navigation to land, so
    # give it a few seconds before reading page.url.)
    page.wait_for_timeout(8_000)
    if "identifier" in page.url or "rejected" in page.url:
        raise ManualLoginRequired(
            f"Account chooser led to a sign-in failure page ({page.url}), not "
            "consent — either the Google session expired or Google's bot "
            "detection rejected the automated sign-in. Run login.py."
        )

    # Google shows one of a few confirm screens here depending on which kind
    # of reauth this is — "Continue" (session refresh) or "Allow" (full scope
    # consent) — or sometimes skips straight through. Try both, best-effort.
    for button_name in ("Continue", "Allow"):
        try:
            page.get_by_role("button", name=button_name).click(timeout=5_000)
            break
        except Exception:
            continue

    # The button click kicks off Voiro's own SSO token exchange (a redirect
    # through /phoenix/systems/login/sso#access_token=... before it lands on
    # /reports) — re-navigating immediately races that in-flight redirect and
    # can land back on the login page before the session cookie is actually set.
    page.wait_for_timeout(5_000)
    page.goto(config.REPORTS_URL, wait_until="networkidle", timeout=PAGE_LOAD_TIMEOUT_MS)
    if "login" in page.url:
        raise RuntimeError("Re-auth click-through completed but still not logged in.")


def attempt_generate_and_download(page):
    """One full pass: load the reports page fresh, fill the form, generate,
    wait for a confirmed-fresh Ready row, download. Raises on any failure —
    the caller decides whether to retry."""
    page.goto(config.REPORTS_URL, wait_until="networkidle", timeout=PAGE_LOAD_TIMEOUT_MS)
    ensure_logged_in(page)

    open_report_pane(page)
    select_report_type(page, REPORT_TYPE)
    set_date_range(page, START_DATE, END_DATE)
    expected_name = read_report_name(page)
    print("Report name shown in the form (our freshness key):", expected_name)
    set_salesperson(page, SALESPERSON)
    ensure_include_org_yes(page)
    click_generate(page)

    row = wait_for_fresh_ready_row(page, REPORT_TYPE, expected_name)
    print("Confirmed fresh Ready row:", row.inner_text().replace("\n", " | "))
    return download_row(page, row)


def main():
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=str(config.PROFILE_DIR),
            channel="chrome",
            headless=True,
            accept_downloads=True,
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.set_default_timeout(DEFAULT_ACTION_TIMEOUT_MS)

        last_error = None
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                print(f"--- Attempt {attempt}/{MAX_ATTEMPTS} ---")
                path = attempt_generate_and_download(page)
                print("DONE:", path)
                ctx.close()
                return path
            except ManualLoginRequired as e:
                # Not retryable — retrying just means more automated hits
                # against Google's login, which risks getting flagged harder.
                print(f"Attempt {attempt} failed ({e!r}) — needs a human, not retrying.")
                ctx.close()
                raise
            except Exception as e:
                last_error = e
                print(f"Attempt {attempt} failed ({e!r}) — retrying from scratch (reload + refill).")
                # Close anything the failed attempt may have popped open
                # (e.g. a stray Google/download tab) but keep the session —
                # the persistent profile means no re-login is needed.
                for extra_page in ctx.pages[1:]:
                    try:
                        extra_page.close()
                    except Exception:
                        pass
                if attempt < MAX_ATTEMPTS:
                    time.sleep(RETRY_BACKOFF_S)

        ctx.close()
        raise RuntimeError(f"All {MAX_ATTEMPTS} attempts failed. Last error: {last_error!r}")


if __name__ == "__main__":
    main()
