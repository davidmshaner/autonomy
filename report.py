# report.py
from __future__ import annotations
import io, csv
from metrics import Row

_HEADERS = ["week of", "cards", "human turns", "spec turns", "spec/card", "actions/steer"]

def _fmt(v: float | None) -> str:
    return "—" if v is None else f"{v:.2f}"

def _cells(r: Row) -> list[str]:
    return [r.week, str(r.cards), str(r.human), str(r.spec),
            _fmt(r.spec_per_card), _fmt(r.actions_per_steer)]

def render_table(rows: list[Row], footer: str) -> str:
    grid = [_HEADERS] + [_cells(r) for r in rows]
    widths = [max(len(row[i]) for row in grid) for i in range(len(_HEADERS))]
    lines = ["  ".join(c.ljust(widths[i]) for i, c in enumerate(row)) for row in grid]
    return "\n".join(lines) + "\n" + footer

def render_csv(rows: list[Row]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["week_of", "cards", "human_turns", "spec_turns", "spec_per_card", "actions_per_steer"])
    for r in rows:
        w.writerow([r.week, r.cards, r.human, r.spec,
                    "" if r.spec_per_card is None else f"{r.spec_per_card:.2f}",
                    "" if r.actions_per_steer is None else f"{r.actions_per_steer:.2f}"])
    return buf.getvalue()

def render_markdown(rows: list[Row], footer: str) -> str:
    head = "| " + " | ".join(_HEADERS) + " |"
    sep = "| " + " | ".join("---" for _ in _HEADERS) + " |"
    body = ["| " + " | ".join(_cells(r)) + " |" for r in rows]
    return "\n".join([head, sep] + body) + f"\n\n_{footer}_\n"
