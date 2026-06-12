# trackers/base.py
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from zoneinfo import ZoneInfo
from timeutil import week_start

@dataclass
class Card:
    id: str
    title: str
    completed_at: datetime   # tz-aware
    author: str | None       # actor who closed/merged; used by the `me` filter

class Tracker(Protocol):
    def list_completed_cards(self, since: datetime, until: datetime) -> list[Card]: ...

def filter_me(cards: list[Card], me: str | None) -> list[Card]:
    if me is None:
        return list(cards)
    return [c for c in cards if c.author == me]

def cards_by_week(cards: list[Card], tz: ZoneInfo) -> dict[str, int]:
    out: dict[str, int] = {}
    for c in cards:
        wk = week_start(c.completed_at, tz)
        out[wk] = out.get(wk, 0) + 1
    return out
