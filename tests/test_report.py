# tests/test_report.py
from __future__ import annotations
from metrics import Row
from report import render_table, render_csv, render_markdown

ROWS = [
    Row("2026-06-01", 41, 337, 108, 2.634, 29.2),
    Row("2026-06-08", 36, 256, 58, 1.611, 79.2),
    Row("2026-06-15", 0, 4, 0, None, None),
]
FOOTER = "scope: repo-root upper bound · github_projects · me=davidmshaner-gi"

def test_render_table_has_header_and_dash_for_none():
    out = render_table(ROWS, FOOTER)
    assert "week of" in out and "actions/steer" in out
    assert "2.63" in out          # spec_per_card rounded
    assert "—" in out             # None rendered as em dash
    assert out.strip().endswith(FOOTER)

def test_render_csv_is_parseable():
    out = render_csv(ROWS)
    lines = out.strip().splitlines()
    assert lines[0] == "week_of,cards,human_turns,spec_turns,spec_per_card,actions_per_steer"
    assert lines[1].startswith("2026-06-01,41,337,108,")
    assert lines[3].endswith(",,")  # None -> empty CSV cells

def test_render_markdown_is_a_table():
    out = render_markdown(ROWS, FOOTER)
    assert out.startswith("| week of |")
    assert "| --- |" in out
    assert FOOTER in out
