from __future__ import annotations
import json, os
from setup.discover import rank_roots

def test_rank_roots_counts_sessions_by_decoded_root(tmp_path):
    base = tmp_path / "projects"
    d1 = base / "-Users-me-dev-alpha"; d1.mkdir(parents=True)
    (d1 / "a.jsonl").write_text("{}\n"); (d1 / "b.jsonl").write_text("{}\n")
    d2 = base / "-Users-me-dev-beta"; d2.mkdir(parents=True)
    (d2 / "c.jsonl").write_text("{}\n")
    ranked = rank_roots(str(base))
    assert ranked[0]["sessions"] == 2
    assert ranked[0]["root"].endswith("alpha")
    assert [r["sessions"] for r in ranked] == [2, 1]
