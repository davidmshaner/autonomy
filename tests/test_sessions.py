# tests/test_sessions.py
from __future__ import annotations
import json, os
from sessions import classify_user_turn, count_tool_actions

FIX = os.path.join(os.path.dirname(__file__), "fixtures", "session_basic.jsonl")

def _lines():
    with open(FIX) as f:
        return [json.loads(l) for l in f if l.strip()]

def test_classify_spec_and_human_and_drops():
    rows = _lines()
    verdicts = [classify_user_turn(r) for r in rows if r.get("type") == "user"]
    # order matches the fixture's user lines:
    # long brief, "go ahead", tool_result, isMeta, isSidechain, command-name, command-stdout, system-reminder
    assert verdicts == ["spec", "human", "drop", "drop", "drop", "drop", "drop", "drop"]

def test_count_tool_actions_counts_each_tool_use_block():
    rows = _lines()
    assistant = [r for r in rows if r.get("type") == "assistant"][0]
    assert count_tool_actions(assistant) == 2

def test_count_tool_actions_zero_for_user():
    rows = _lines()
    user = [r for r in rows if r.get("type") == "user"][0]
    assert count_tool_actions(user) == 0

# append to tests/test_sessions.py
from sessions import session_in_scope, aggregate_sessions
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

def test_session_in_scope_prefix_match(tmp_path):
    assert session_in_scope("/Users/me/dev/proj/sub", ["/Users/me/dev/proj"]) is True
    assert session_in_scope("/Users/me/dev/other", ["/Users/me/dev/proj"]) is False

def test_aggregate_sessions_buckets_by_week(tmp_path):
    # Point a projects dir at the fixture file inside an encoded-style subdir.
    proj = tmp_path / "-Users-me-dev-proj"
    proj.mkdir()
    (proj / "s.jsonl").write_text(open(FIX).read())
    since = datetime(2026, 6, 1, tzinfo=timezone.utc)
    until = datetime(2026, 6, 15, tzinfo=timezone.utc)
    agg = aggregate_sessions(
        projects_dirs=[str(tmp_path)],
        repo_roots=["/Users/me/dev/proj"],
        tz=ZoneInfo("America/New_York"),
        since=since, until=until, spec_min_chars=160,
    )
    wk = agg["2026-06-08"]
    assert wk["human"] == 2 and wk["spec"] == 1 and wk["actions"] == 2
