"""Shared config for the Voiro report automation."""
import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent

# Dedicated Chrome profile — keeps the Voiro/Google session separate from your
# real Chrome. Log in once (login.py) and every run reuses the saved cookies.
PROFILE_DIR = BASE / "chrome-profile"

# Where downloaded .xlsx reports land.
DOWNLOAD_DIR = BASE / "downloads"

# Where run status / watchdog logs land.
LOGS_DIR = BASE / "logs"

REPORTS_URL = "https://paytm.voiro.com/phoenix/reports"

# Destination Google Sheet. Update SHEET_URL if you version up the workbook
# (paste the new sheet's URL straight from the browser address bar) — the
# tab name below does NOT change when the sheet is versioned.
SHEET_URL = "https://docs.google.com/spreadsheets/d/12wW_O36TQTYuc2NT-oFnKWa6IRzNuHmw0eCoTTyZknE/edit?gid=1636204745#gid=1636204745"
SHEET_TAB = "Raw MT Data"

# Service-account creds for writing to the sheet.
SA_CREDS = BASE / "service-account.json"

# Google account used for the lightweight re-auth click-through (see
# ensure_logged_in in generate_meeting_report.py) when Google's periodic
# OAuth reauth screen appears — never needs a password, just this account tile.
GOOGLE_ACCOUNT_EMAIL = "amritansh.ashesh@paytm.com"

# Meeting Report generation settings.
SALESPERSON = "Anshul Batra"  # top of hierarchy; report includes everyone under them
START_DATE = datetime.date(2026, 6, 1)  # initiative start date — fixed, doesn't move
END_DATE = datetime.date.today()  # always "today" as of whenever this runs
