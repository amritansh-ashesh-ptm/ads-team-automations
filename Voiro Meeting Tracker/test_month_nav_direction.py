"""Self-check for _month_nav_direction: today's bug was the end pane silently
landing on the wrong month (July instead of August) because start/end were
more than one month apart — this is the direction logic that replaced the
old "assume the end pane already shows the right month" shortcut.

    .venv/bin/python test_pick_end_pane_day_cell.py
"""
from generate_meeting_report import _month_nav_direction


def test_target_ahead_goes_next():
    assert _month_nav_direction((2026, 7), (2026, 8)) == "next"


def test_target_behind_goes_previous():
    assert _month_nav_direction((2026, 8), (2026, 6)) == "previous"


def test_target_reached_stops():
    assert _month_nav_direction((2026, 8), (2026, 8)) is None


def test_year_boundary_goes_next():
    assert _month_nav_direction((2026, 12), (2027, 1)) == "next"


if __name__ == "__main__":
    test_target_ahead_goes_next()
    test_target_behind_goes_previous()
    test_target_reached_stops()
    test_year_boundary_goes_next()
    print("OK")
