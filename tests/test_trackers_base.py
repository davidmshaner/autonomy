# tests/test_trackers_base.py
from __future__ import annotations
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from trackers.base import Card, filter_me, cards_by_week

def _card(title, day, author):
    return Card(id=title, title=title,
                completed_at=datetime(2026, 6, day, 12, 0, tzinfo=timezone.utc),
                author=author)

def test_filter_me_keeps_only_my_cards():
    cards = [_card("a", 9, "me"), _card("b", 9, "someone")]
    assert [c.title for c in filter_me(cards, "me")] == ["a"]

def test_filter_me_none_keeps_all():
    cards = [_card("a", 9, "me"), _card("b", 9, "someone")]
    assert len(filter_me(cards, None)) == 2

def test_cards_by_week_counts_per_monday():
    cards = [_card("a", 9, "me"), _card("b", 10, "me"), _card("c", 2, "me")]
    by = cards_by_week(cards, ZoneInfo("America/New_York"))
    assert by["2026-06-08"] == 2
    assert by["2026-06-01"] == 1
