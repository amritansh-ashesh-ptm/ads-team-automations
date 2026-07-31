"""Self-check for the bootstrap-race fix in ensure_logged_in: it must not
trust the URL immediately after goto (the SPA shows /reports for a moment
even when logged out) — it must wait for either the toggle (really logged
in) or a real /login URL (needs re-auth).

    .venv/bin/python test_ensure_logged_in.py
"""
from generate_meeting_report import ensure_logged_in


class FakeLocator:
    def __init__(self, present_after):
        self.present_after = present_after  # list of bools, one per poll
        self.calls = 0

    def count(self):
        val = self.present_after[min(self.calls, len(self.present_after) - 1)]
        self.calls += 1
        return 1 if val else 0


class FakePage:
    def __init__(self, url, toggle_present_after):
        self.url = url
        self._toggle = FakeLocator(toggle_present_after)
        self.reauth_attempted = False

    def locator(self, selector):
        assert selector == "a.cursor.ps-4"
        return self._toggle

    def get_by_text(self, *a, **k):
        self.reauth_attempted = True
        raise RuntimeError("stop here — reauth path reached, that's what we're checking")


def test_toggle_present_returns_without_reauth():
    page = FakePage(url="https://paytm.voiro.com/phoenix/reports", toggle_present_after=[True])
    ensure_logged_in(page)  # must return cleanly, no exception
    assert not page.reauth_attempted


def test_race_then_real_login_triggers_reauth():
    # URL still shows /reports on the first poll (bootstrap race), toggle
    # never shows up because the SPA is about to redirect to /login.
    page = FakePage(url="https://paytm.voiro.com/phoenix/reports", toggle_present_after=[False, False])

    def flipping_url_check():
        page.url = "https://paytm.voiro.com/phoenix/systems/login?returnUrl=/reports"

    orig_count = page._toggle.count
    def count_then_flip():
        result = orig_count()
        flipping_url_check()
        return result
    page._toggle.count = count_then_flip

    try:
        ensure_logged_in(page)
        raised = False
    except RuntimeError as e:
        raised = "reauth path reached" in str(e)
    assert raised, "expected fall-through into the re-auth flow, not a silent return"


if __name__ == "__main__":
    test_toggle_present_returns_without_reauth()
    test_race_then_real_login_triggers_reauth()
    print("OK")
