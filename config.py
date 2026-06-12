# config.py
from __future__ import annotations
import yaml

class ConfigError(Exception):
    pass

def load_config(path: str) -> dict:
    try:
        with open(path) as f:
            cfg = yaml.safe_load(f) or {}
    except FileNotFoundError:
        raise ConfigError(f"config not found: {path} (copy config.example.yaml -> config.yaml)")

    for key in ("timezone", "projects_dirs", "scope", "tracker"):
        if key not in cfg:
            raise ConfigError(f"config missing required key: {key}")
    if "repo_roots" not in cfg["scope"]:
        raise ConfigError("config missing scope.repo_roots")

    cfg.setdefault("week_start", "monday")
    cfg.setdefault("spec_turn_min_chars", 160)

    t = cfg["tracker"]
    if "type" not in t or "token_env" not in t:
        raise ConfigError("tracker requires type and token_env")
    if t["type"] == "github_projects":
        if "project_node_id" not in t:
            raise ConfigError("github_projects tracker requires project_node_id")
        t.setdefault("done_status", ["Done"])
    elif t["type"] == "linear":
        if "team_id" not in t:
            raise ConfigError("linear tracker requires team_id")
    else:
        raise ConfigError(f"unknown tracker type '{t['type']}' (expected github_projects|linear)")
    t.setdefault("me", None)
    return cfg
