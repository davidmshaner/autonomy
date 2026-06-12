from __future__ import annotations
import json
import os
import sys

def _decode(slug: str) -> str:
    """Best-effort decode of a Claude Code project-dir slug back to a path."""
    return slug.replace("-", "/", ) if slug.startswith("-") else slug

def rank_roots(projects_dir: str) -> list[dict]:
    """Rank encoded session subdirs by .jsonl count (candidate work roots)."""
    out = []
    if not os.path.isdir(projects_dir):
        return out
    for name in os.listdir(projects_dir):
        sub = os.path.join(projects_dir, name)
        if not os.path.isdir(sub):
            continue
        n = sum(1 for f in os.listdir(sub) if f.endswith(".jsonl"))
        if n:
            out.append({"root": _decode(name), "slug": name, "sessions": n})
    out.sort(key=lambda r: r["sessions"], reverse=True)
    return out

def discover() -> dict:
    home = os.path.expanduser("~")
    cc = os.path.join(home, ".claude", "projects")
    if sys.platform == "darwin":
        cowork = os.path.join(home, "Library", "Application Support", "Claude",
                              "local-agent-mode-sessions")
    else:
        cowork = os.path.join(home, ".claude", "local-agent-mode-sessions")
    return {
        "os": sys.platform,
        "projects_dir": cc,
        "projects_dir_exists": os.path.isdir(cc),
        "cowork_dir": cowork,
        "cowork_dir_exists": os.path.isdir(cowork),
        "candidate_roots": rank_roots(cc)[:15],
    }

if __name__ == "__main__":
    print(json.dumps(discover(), indent=2))
