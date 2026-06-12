# timeutil.py
from __future__ import annotations
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

def parse_ts(s: str) -> datetime:
    """Parse an ISO8601 timestamp (with 'Z' or numeric offset) to a tz-aware datetime."""
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    return datetime.fromisoformat(s)

def week_start(dt: datetime, tz: ZoneInfo) -> str:
    """ISO-date (YYYY-MM-DD) of the Monday that begins dt's week, in local tz."""
    local = dt.astimezone(tz)
    monday = local - timedelta(days=local.weekday())
    return monday.strftime("%Y-%m-%d")
