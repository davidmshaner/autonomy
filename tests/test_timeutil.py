# tests/test_timeutil.py
from __future__ import annotations
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from timeutil import parse_ts, week_start

def test_parse_ts_handles_z_suffix():
    dt = parse_ts("2026-06-08T13:30:00.000Z")
    assert dt.tzinfo is not None
    assert dt.astimezone(timezone.utc).hour == 13

def test_parse_ts_handles_offset():
    dt = parse_ts("2026-06-08T09:30:00-04:00")
    assert dt.astimezone(timezone.utc).hour == 13

def test_week_start_is_monday_in_local_tz():
    tz = ZoneInfo("America/New_York")
    # 2026-06-10 is a Wednesday; its week starts Monday 2026-06-08
    dt = datetime(2026, 6, 10, 18, 0, tzinfo=timezone.utc)
    assert week_start(dt, tz) == "2026-06-08"

def test_week_start_respects_local_day_boundary():
    tz = ZoneInfo("America/New_York")
    # 2026-06-08 00:30 UTC is still Sunday 2026-06-07 20:30 local -> week of 2026-06-01
    dt = datetime(2026, 6, 8, 0, 30, tzinfo=timezone.utc)
    assert week_start(dt, tz) == "2026-06-01"
