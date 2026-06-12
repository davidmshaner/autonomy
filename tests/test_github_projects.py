# tests/test_github_projects.py
from __future__ import annotations
import json, os
from datetime import datetime, timezone
from trackers.github_projects import parse_items

FIX = os.path.join(os.path.dirname(__file__), "fixtures", "github_items.json")
SINCE = datetime(2026, 6, 1, tzinfo=timezone.utc)
UNTIL = datetime(2026, 6, 15, tzinfo=timezone.utc)

def test_parse_items_picks_done_cards_only():
    nodes = json.load(open(FIX))
    cards = parse_items(nodes, done_status=["Done"], since=SINCE, until=UNTIL, me=None)
    titles = sorted(c.title for c in cards)
    assert titles == ["Closed issue card", "Merged PR card"]

def test_parse_items_sets_author_and_completed_at():
    nodes = json.load(open(FIX))
    cards = {c.title: c for c in parse_items(nodes, ["Done"], SINCE, UNTIL, None)}
    assert cards["Merged PR card"].author == "me"
    assert cards["Merged PR card"].completed_at == datetime(2026, 6, 9, 15, 0, tzinfo=timezone.utc)
    assert cards["Closed issue card"].author == "someone"

def test_parse_items_me_filter():
    nodes = json.load(open(FIX))
    cards = parse_items(nodes, ["Done"], SINCE, UNTIL, me="me")
    assert [c.title for c in cards] == ["Merged PR card"]

def test_parse_items_window_excludes_outside():
    nodes = json.load(open(FIX))
    cards = parse_items(nodes, ["Done"], SINCE, datetime(2026, 6, 9, 20, 0, tzinfo=timezone.utc), None)
    assert [c.title for c in cards] == ["Merged PR card"]  # issue closed 6/10 is now outside
