# tests/test_linear.py
from __future__ import annotations
import json, os
from datetime import datetime, timezone
from trackers.linear import parse_issues

FIX = os.path.join(os.path.dirname(__file__), "fixtures", "linear_issues.json")
SINCE = datetime(2026, 6, 1, tzinfo=timezone.utc)
UNTIL = datetime(2026, 6, 15, tzinfo=timezone.utc)

def test_parse_issues_completed_only():
    nodes = json.load(open(FIX))
    cards = sorted(c.title for c in parse_issues(nodes, SINCE, UNTIL, None))
    assert cards == ["Completed assigned", "Completed unassigned"]

def test_parse_issues_author_is_assignee_else_creator():
    nodes = json.load(open(FIX))
    by = {c.title: c for c in parse_issues(nodes, SINCE, UNTIL, None)}
    assert by["Completed assigned"].author == "brian@example.com"
    assert by["Completed unassigned"].author == "someone@example.com"  # falls back to creator

def test_parse_issues_me_filter():
    nodes = json.load(open(FIX))
    cards = parse_issues(nodes, SINCE, UNTIL, me="brian@example.com")
    assert [c.title for c in cards] == ["Completed assigned"]
