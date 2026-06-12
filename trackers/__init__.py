# trackers/__init__.py
from __future__ import annotations
import os
from trackers.base import Tracker

def get_tracker(cfg: dict) -> Tracker:
    """Build a Tracker from the validated `tracker` config block."""
    t = cfg["type"]
    token = os.environ.get(cfg["token_env"], "")
    if not token:
        raise SystemExit(
            f"autonomy: tracker token env var '{cfg['token_env']}' is empty. "
            f"Set it: export {cfg['token_env']}=<your token>"
        )
    if t == "github_projects":
        from trackers.github_projects import GitHubProjectsTracker
        return GitHubProjectsTracker(token, cfg["project_node_id"],
                                     cfg.get("done_status", ["Done"]), cfg.get("me"))
    if t == "linear":
        from trackers.linear import LinearTracker
        return LinearTracker(token, cfg["team_id"], cfg.get("me"))
    raise SystemExit(f"autonomy: unknown tracker type '{t}' (expected github_projects|linear)")
