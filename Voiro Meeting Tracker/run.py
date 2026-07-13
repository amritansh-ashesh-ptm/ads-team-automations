"""Full pipeline: generate + download the Meeting Report, then push it to
the Google Sheet. Writes logs/last_run.json (timestamp + success/failure)
so check_run.py can detect a missed or failed scheduled run.

    .venv/bin/python run.py
"""
import datetime
import json

import check_run
import config
import generate_meeting_report
import push_to_sheet


def _write_status(status, error=None):
    config.LOGS_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"timestamp": datetime.datetime.now().isoformat(), "status": status}
    if error:
        payload["error"] = error
    (config.LOGS_DIR / "last_run.json").write_text(json.dumps(payload))


def _prune_old_downloads():
    """Only today's report is ever needed for a spot-check; delete the rest."""
    today = datetime.date.today()
    for f in config.DOWNLOAD_DIR.glob("*.xlsx"):
        if datetime.date.fromtimestamp(f.stat().st_mtime) != today:
            f.unlink()


def main():
    try:
        path = generate_meeting_report.main()
        _prune_old_downloads()
        push_to_sheet.push(path)
        _write_status("success")
        check_run.notify("You're all set! The Voiro Meeting Tracker has been updated successfully")
    except Exception as e:
        _write_status("failure", error=repr(e))
        check_run.notify(f"Today's report run failed: {e!r}. Run 'automations' in a terminal to trigger it manually.")
        raise


if __name__ == "__main__":
    main()
