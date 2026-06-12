# tests/test_cli.py
from __future__ import annotations
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import autonomy as cli

def test_window_weeks_spans_back_from_until():
    until = datetime(2026, 6, 12, 12, 0, tzinfo=timezone.utc)
    since, end = cli.window(weeks=2, since=None, now=until)
    assert end == until
    assert (until - since).days == 14

def test_window_explicit_since_overrides_weeks():
    until = datetime(2026, 6, 12, tzinfo=timezone.utc)
    since, end = cli.window(weeks=6, since="2026-05-01", now=until)
    assert since == datetime(2026, 5, 1, tzinfo=timezone.utc)

def test_build_footer_mentions_scope_and_tracker():
    cfg = {"tracker": {"type": "github_projects", "me": "davidmshaner-gi"}}
    f = cli.build_footer(cfg)
    assert "upper bound" in f and "github_projects" in f and "davidmshaner-gi" in f
