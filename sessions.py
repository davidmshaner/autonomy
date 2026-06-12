# sessions.py
from __future__ import annotations
import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo
from timeutil import parse_ts, week_start

SPEC_MIN_CHARS_DEFAULT = 160

# Harness/command wrappers that mean "not a genuine human steering turn".
_INJECTION_MARKERS = (
    "<command-name>", "<command-message>", "<command-args>",
    "<local-command-stdout>", "<local-command-caveat>",
    "<skill_md>", "<task-notification>", "<system-reminder>",
    "<bash-stdout>", "<bash-stderr>",
)

def _text_of(entry: dict) -> str:
    """Flatten a user message's content to plain text; '' if it is a tool_result."""
    msg = entry.get("message") or {}
    content = msg.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "tool_result":
                return ""  # tool_result entries are never human turns
            if block.get("type") == "text":
                parts.append(block.get("text", ""))
        return "".join(parts)
    return ""

def classify_user_turn(entry: dict, spec_min_chars: int = SPEC_MIN_CHARS_DEFAULT) -> str:
    """Return 'spec', 'human', or 'drop' for a single JSONL entry."""
    if entry.get("type") != "user":
        return "drop"
    if entry.get("isMeta") or entry.get("isSidechain"):
        return "drop"
    text = _text_of(entry)
    if not text.strip():
        return "drop"  # tool_result or empty
    stripped = text.lstrip()
    if any(stripped.startswith(m) for m in _INJECTION_MARKERS):
        return "drop"
    return "spec" if len(text) >= spec_min_chars else "human"

def count_tool_actions(entry: dict) -> int:
    """Number of tool_use blocks in an assistant message (0 for anything else)."""
    if entry.get("type") != "assistant":
        return 0
    content = (entry.get("message") or {}).get("content")
    if not isinstance(content, list):
        return 0
    return sum(1 for b in content if isinstance(b, dict) and b.get("type") == "tool_use")

# append to sessions.py
def _expand(p: str) -> str:
    return os.path.abspath(os.path.expanduser(p))

def session_in_scope(cwd: str, repo_roots: list[str]) -> bool:
    cwd = _expand(cwd)
    return any(cwd == r or cwd.startswith(r + os.sep) for r in (_expand(x) for x in repo_roots))

def _iter_entries(path: str):
    with open(path, "r", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue

def _session_cwd(path: str) -> str | None:
    for entry in _iter_entries(path):
        cwd = entry.get("cwd")
        if cwd:
            return cwd
    return None

def aggregate_sessions(projects_dirs: list[str], repo_roots: list[str], tz: ZoneInfo,
                       since: datetime, until: datetime,
                       spec_min_chars: int = SPEC_MIN_CHARS_DEFAULT) -> dict:
    """Walk JSONL under projects_dirs, keep in-scope sessions, bucket counts by week."""
    weeks: dict[str, dict[str, int]] = {}
    def bump(wk: str, key: str, n: int = 1):
        weeks.setdefault(wk, {"human": 0, "spec": 0, "actions": 0})[key] += n

    for base in projects_dirs:
        base = _expand(base)
        if not os.path.isdir(base):
            continue
        for root, _dirs, files in os.walk(base):
            for name in files:
                if not name.endswith(".jsonl"):
                    continue
                path = os.path.join(root, name)
                cwd = _session_cwd(path)
                if not cwd or not session_in_scope(cwd, repo_roots):
                    continue
                for entry in _iter_entries(path):
                    ts = entry.get("timestamp")
                    if not ts:
                        continue
                    try:
                        dt = parse_ts(ts)
                    except ValueError:
                        continue
                    if not (since <= dt <= until):
                        continue
                    wk = week_start(dt, tz)
                    verdict = classify_user_turn(entry, spec_min_chars)
                    if verdict == "spec":
                        bump(wk, "human"); bump(wk, "spec")
                    elif verdict == "human":
                        bump(wk, "human")
                    else:
                        actions = count_tool_actions(entry)
                        if actions:
                            bump(wk, "actions", actions)
    return weeks
