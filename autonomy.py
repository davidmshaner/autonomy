# autonomy.py
from __future__ import annotations
import argparse
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from config import load_config, ConfigError
from trackers import get_tracker
from trackers.base import cards_by_week
from sessions import aggregate_sessions
from metrics import build_rows
from report import render_table, render_csv, render_markdown

def window(weeks: int, since: str | None, now: datetime) -> tuple[datetime, datetime]:
    if since:
        start = datetime.fromisoformat(since).replace(tzinfo=timezone.utc)
        return start, now
    return now - timedelta(weeks=weeks), now

def build_footer(cfg: dict) -> str:
    t = cfg["tracker"]
    me = t.get("me")
    me_part = f" · me={me}" if me else ""
    return f"scope: repo-root upper bound · {t['type']}{me_part}"

def run(cfg: dict, weeks: int, since: str | None, now: datetime) -> list:
    tz = ZoneInfo(cfg["timezone"])
    start, end = window(weeks, since, now)
    tracker = get_tracker(cfg["tracker"])
    cards = tracker.list_completed_cards(start, end)
    cbw = cards_by_week(cards, tz)
    sbw = aggregate_sessions(cfg["projects_dirs"], cfg["scope"]["repo_roots"], tz,
                             start, end, cfg["spec_turn_min_chars"])
    return build_rows(cbw, sbw)

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="autonomy", description="Weekly agent-autonomy meter.")
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--weeks", type=int, default=6)
    ap.add_argument("--since", default=None, help="ISO date (YYYY-MM-DD); overrides --weeks")
    ap.add_argument("--csv", default=None, help="also write CSV to this path")
    ap.add_argument("--md", default=None, help="also write Markdown to this path")
    args = ap.parse_args(argv)
    try:
        cfg = load_config(args.config)
    except ConfigError as e:
        print(f"autonomy: {e}")
        return 2
    now = datetime.now(timezone.utc)
    rows = run(cfg, args.weeks, args.since, now)
    footer = build_footer(cfg)
    print(render_table(rows, footer))
    if args.csv:
        with open(args.csv, "w") as f:
            f.write(render_csv(rows))
    if args.md:
        with open(args.md, "w") as f:
            f.write(render_markdown(rows, footer))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
