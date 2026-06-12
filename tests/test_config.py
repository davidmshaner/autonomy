# tests/test_config.py
from __future__ import annotations
import pytest
from config import load_config, ConfigError

BASE = {
    "timezone": "America/New_York",
    "projects_dirs": ["~/x"],
    "scope": {"repo_roots": ["~/dev/proj"]},
    "tracker": {"type": "github_projects", "token_env": "T", "project_node_id": "PVT_x"},
}

def test_load_config_defaults_and_resolves(tmp_path):
    p = tmp_path / "c.yaml"
    import yaml; p.write_text(yaml.safe_dump(BASE))
    cfg = load_config(str(p))
    assert cfg["spec_turn_min_chars"] == 160          # default applied
    assert cfg["tracker"]["done_status"] == ["Done"]   # default applied
    assert cfg["week_start"] == "monday"

def test_github_requires_project_node_id(tmp_path):
    bad = {**BASE, "tracker": {"type": "github_projects", "token_env": "T"}}
    p = tmp_path / "c.yaml"; import yaml; p.write_text(yaml.safe_dump(bad))
    with pytest.raises(ConfigError, match="project_node_id"):
        load_config(str(p))

def test_linear_requires_team_id(tmp_path):
    bad = {**BASE, "tracker": {"type": "linear", "token_env": "T"}}
    p = tmp_path / "c.yaml"; import yaml; p.write_text(yaml.safe_dump(bad))
    with pytest.raises(ConfigError, match="team_id"):
        load_config(str(p))

def test_unknown_tracker_type(tmp_path):
    bad = {**BASE, "tracker": {"type": "jira", "token_env": "T"}}
    p = tmp_path / "c.yaml"; import yaml; p.write_text(yaml.safe_dump(bad))
    with pytest.raises(ConfigError, match="github_projects|linear"):
        load_config(str(p))
