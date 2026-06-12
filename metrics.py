# metrics.py
from __future__ import annotations
from dataclasses import dataclass

@dataclass
class Row:
    week: str
    cards: int
    human: int
    spec: int
    spec_per_card: float | None
    actions_per_steer: float | None

def _safe_div(num: int, den: int) -> float | None:
    return (num / den) if den else None

def build_rows(cards_by_week: dict[str, int], sessions_by_week: dict[str, dict]) -> list[Row]:
    weeks = sorted(set(cards_by_week) | set(sessions_by_week))
    rows: list[Row] = []
    for wk in weeks:
        c = cards_by_week.get(wk, 0)
        s = sessions_by_week.get(wk, {"human": 0, "spec": 0, "actions": 0})
        rows.append(Row(
            week=wk, cards=c, human=s["human"], spec=s["spec"],
            spec_per_card=_safe_div(s["spec"], c),
            actions_per_steer=_safe_div(s["actions"], s["human"]),
        ))
    return rows
