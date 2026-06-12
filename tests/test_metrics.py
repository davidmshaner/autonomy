# tests/test_metrics.py
from __future__ import annotations
from metrics import build_rows, Row

def test_build_rows_joins_and_computes():
    cards = {"2026-06-08": 16, "2026-06-01": 41}
    sessions = {"2026-06-08": {"human": 222, "spec": 72, "actions": 6860},
                "2026-06-01": {"human": 337, "spec": 108, "actions": 9840}}
    rows = build_rows(cards, sessions)
    r = {row.week: row for row in rows}
    assert r["2026-06-08"].cards == 16
    assert r["2026-06-08"].spec_per_card == 4.5
    assert round(r["2026-06-08"].actions_per_steer, 1) == 30.9
    # rows are sorted ascending by week
    assert [row.week for row in rows] == ["2026-06-01", "2026-06-08"]

def test_build_rows_zero_cards_yields_none_ratios():
    cards = {}  # a week with sessions but no completed cards
    sessions = {"2026-06-08": {"human": 10, "spec": 2, "actions": 50}}
    rows = build_rows(cards, sessions)
    assert rows[0].cards == 0
    assert rows[0].spec_per_card is None          # no divide-by-zero
    assert round(rows[0].actions_per_steer, 1) == 5.0

def test_build_rows_zero_human_yields_none_actions_per_steer():
    rows = build_rows({"2026-06-08": 3}, {"2026-06-08": {"human": 0, "spec": 0, "actions": 0}})
    assert rows[0].actions_per_steer is None
