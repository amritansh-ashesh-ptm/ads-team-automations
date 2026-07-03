"""Watchdog: on weekdays, if today's 10:05am run hasn't succeeded by 10:25am,
fire a macOS notification. Meant to run on a launchd StartInterval (every
~30 min) — since launchd catches up missed interval timers right after the
Mac wakes from sleep, this notification shows up shortly after you next open
the laptop, without needing a real wake-from-sleep hook.

Throttled to one notification per day (logs/last_alert_date.txt) so a
still-broken job doesn't re-notify every 30 minutes.

    .venv/bin/python check_run.py
"""
import datetime
import json
import subprocess

import config

ALERT_AFTER_HOUR = 10
ALERT_AFTER_MINUTE = 25  # 20 min after the 10:05 scheduled run


def notify(message):
    subprocess.run(
        ["osascript", "-e", f'display notification "{message}" with title "Voiro Meeting Tracker"'],
        check=False,
    )


def already_alerted_today(today_str):
    marker = config.LOGS_DIR / "last_alert_date.txt"
    return marker.exists() and marker.read_text().strip() == today_str


def mark_alerted(today_str):
    (config.LOGS_DIR / "last_alert_date.txt").write_text(today_str)


def main():
    now = datetime.datetime.now()
    if now.weekday() > 4:  # Sat/Sun
        return
    if (now.hour, now.minute) < (ALERT_AFTER_HOUR, ALERT_AFTER_MINUTE):
        return

    today_str = now.date().isoformat()
    if already_alerted_today(today_str):
        return

    status_file = config.LOGS_DIR / "last_run.json"
    if not status_file.exists():
        problem = "never ran"
    else:
        last_run = json.loads(status_file.read_text())
        run_date = last_run["timestamp"][:10]
        if run_date != today_str:
            problem = "hasn't run today"
        elif last_run["status"] != "success":
            problem = f"failed: {last_run.get('error', 'unknown error')}"
        else:
            problem = None

    if problem:
        notify(f"Today's report run {problem}. Run 'voiro-run' in a terminal to trigger it manually.")
        config.LOGS_DIR.mkdir(parents=True, exist_ok=True)
        mark_alerted(today_str)


if __name__ == "__main__":
    main()
