"""Self-check for _pick_end_pane_day_cell: today's run failed because
start_date=June 1 has no 31st, so only the end pane's day-31 cell ever
matches — that must be accepted, not treated as an error.

    .venv/bin/python test_pick_end_pane_day_cell.py
"""
from generate_meeting_report import _pick_end_pane_day_cell


def test_two_candidates_picks_rightmost():
    start_cell, end_cell = {"x": 10}, {"x": 500}
    assert _pick_end_pane_day_cell([start_cell, end_cell], "15") is end_cell


def test_one_candidate_is_accepted_as_end_pane():
    end_cell = {"x": 500}
    assert _pick_end_pane_day_cell([end_cell], "31") is end_cell


def test_zero_candidates_raises():
    try:
        _pick_end_pane_day_cell([], "31")
        raised = False
    except RuntimeError:
        raised = True
    assert raised


if __name__ == "__main__":
    test_two_candidates_picks_rightmost()
    test_one_candidate_is_accepted_as_end_pane()
    test_zero_candidates_raises()
    print("OK")
