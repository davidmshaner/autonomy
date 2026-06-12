# Autonomy Meter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `autonomy`, a self-contained local CLI that prints a weekly table of agent-autonomy metrics by joining a card tracker (GitHub Projects or Linear) with Claude Code session logs.

**Architecture:** Deterministic pipeline, no LLM in the path. A tracker adapter yields completed `Card`s; a session reader classifies genuine human turns and counts tool-use actions from JSONL, scoped to repo roots; a metrics layer joins both by ISO week; a report layer renders stdout/CSV/Markdown. Mirrors Pulse's self-contained, config-driven, Claude-Code-self-setup shape.

**Tech Stack:** Python 3.9+ (stdlib `zoneinfo`, `argparse`, `json`, `dataclasses`), `pyyaml`, `requests`, `pytest` (dev). Every module starts with `from __future__ import annotations` so PEP 604/585 type hints (`str | None`, `list[Card]`) work on Python 3.9.

**Spec:** `docs/specs/2026-06-12-autonomy-meter-design.md`

---

## Gotcha Pre-Mortem

- **G1** (Cowork connector auth): ADDRESSED. The only Cowork interaction anywhere in the build is read-only ingestion of local session JSONL files from disk — there is no connector, OAuth, magic-link, or loopback listener, so the auth failure G1 guards against cannot occur.
- **G2** (External API on the production request path): N/A. There is no Cloudflare Worker and no broker request path. This is a local CLI; the tracker adapters call GitHub/Linear APIs directly from the user's machine by design. No CF egress, no WAF surface. Traced transitively — the only network calls are `requests.post` in `trackers/github_projects.py` and `trackers/linear.py`, both local-machine to vendor API.
- **G3** (D1 prod/staging parity): N/A. No D1, no database, no migrations. State is local files only.
- **G4** (Cloudflare / wrangler credential resolution): N/A. No task shells out to wrangler.
- **G7** (Fast inner validation loop): ADDRESSED. The session reader is the only potentially slow component (walking many JSONL files). All session/metric logic is unit-tested against tiny in-repo fixtures (Tasks 3, 7) — the fast inner loop. A single-session smoke (`--weeks 1` against one fixture session) precedes any full multi-week scan; Task 10 wires `--weeks` so a 1-week window is the natural small sample. No full-corpus run is required to debug.
- **G8** (GitHub account / repo resolution): ADDRESSED in Task 12 (create + push `davidmshaner/autonomy`). The repo is owned by the `davidmshaner` account, the default per root CLAUDE.md, so no switch is needed — but Task 12 still runs `gh auth status` / `gh auth switch --user davidmshaner` explicitly before the push and embeds the rule that `Repository not found` means wrong account, never a missing repo. The adapter's GitHub Projects token is a PAT read from an env var (`config.token_env`), not a gh/git operation, so G8 does not apply to it.
- **G9** (wrangler token to nested subprocess): N/A. No wrangler, no script shelling out to wrangler.
- **G10** (Bulk D1 loads): N/A. No D1 loads of any size.
- **G11** (gi-plugins bump + push): N/A. `autonomy` is a standalone personal repo, not a `lee-internal-comps` / `lee-raleigh-mcp` broker capability. Its `setup/SKILL.md` is a local Claude Code setup skill in its own repo, not a Cowork broker-discovery plugin.
- **G12** (SKILL.md frontmatter router contract): N/A. There is no `plugins/*/skills/*/helpers.py` and no Cowork plugin router. The build does create `setup/SKILL.md`; Task 12 writes its `description` to accurately match what setup does, but there is no helpers.py capability/version contract to keep in sync.
- **G13** (Dealius MM/DD/YYYY TEXT dates): N/A. No Dealius data, no `*_comps_safe` views. All dates handled are ISO8601 timestamps from JSONL and tracker APIs, parsed via a single tested helper.
- **G14** (Paid-API run cost): N/A. The GitHub GraphQL API and the Linear API are free (rate-limited, not metered per-1k-request SKUs). No per-request-billed service is on any path. Per-run dollar cost is $0.

---

## File Structure

```
autonomy/
  config.example.yaml      # reference config (copied -> config.yaml, gitignored)
  config.py                # load + validate + path-resolve config
  timeutil.py              # tz-aware timestamp parse + ISO-week bucketing (shared by sessions/metrics/trackers)
  sessions.py              # JSONL walk, repo-root scope, turn classification, tool-action count -> weekly aggregates
  trackers/
    __init__.py            # get_tracker(config) factory
    base.py                # Card dataclass, Tracker protocol, filter_me, cards_by_week
    github_projects.py     # fetch (live) + parse_items (pure) -> list[Card]
    linear.py              # fetch (live) + parse_issues (pure) -> list[Card]
  metrics.py               # join cards x sessions by week -> rows of 5 columns
  report.py                # rows -> stdout table / CSV / Markdown + scope footer
  autonomy.py              # argparse CLI entrypoint, wires the pipeline
  setup/
    discover.py            # machine discovery -> JSON
    SKILL.md               # Claude Code self-setup skill
  tests/
    __init__.py
    fixtures/
      session_basic.jsonl          # genuine turns, tool_result, isMeta, isSidechain, markers, assistant tool_use
      github_items.json            # recorded ProjectV2 items payload
      linear_issues.json           # recorded Linear issues payload
    test_config.py
    test_timeutil.py
    test_sessions.py
    test_trackers_base.py
    test_github_projects.py
    test_linear.py
    test_metrics.py
    test_report.py
    test_discover.py
  requirements.txt
  pytest.ini
  README.md
  .gitignore               # already committed: config.yaml, __pycache__, *.pyc, .cache, .DS_Store
```

Files split by responsibility. `timeutil.py` exists so tz/week logic is defined once and reused, never re-derived. Each tracker adapter splits a pure `parse_*` function (unit-tested against a recorded fixture) from a thin live `fetch_*` (no test, just an HTTP call), so no test ever hits the network.

---

## Task 1: Repo scaffold + tooling baseline

**Files:**
- Create: `requirements.txt`, `pytest.ini`, `tests/__init__.py`, `trackers/__init__.py`, `setup/__init__.py`

- [ ] **Step 1: Create `requirements.txt`**

```
pyyaml>=6.0
requests>=2.28
```

- [ ] **Step 2: Create `pytest.ini`**

```ini
[pytest]
testpaths = tests
python_files = test_*.py
```

- [ ] **Step 3: Create empty package markers**

Create `tests/__init__.py` (empty), `setup/__init__.py` (empty). Create `trackers/__init__.py` with a placeholder line (the factory lands in Task 5):

```python
from __future__ import annotations
# get_tracker() factory is added in Task 5.
```

- [ ] **Step 4: Install dev deps and verify pytest runs**

Run: `cd ~/dev/autonomy && python3 -m pip install -r requirements.txt pytest && python3 -m pytest -q`
Expected: `no tests ran` (exit 5) — confirms pytest is installed and the layout is discoverable.

- [ ] **Step 5: Commit**

```bash
cd ~/dev/autonomy
git add requirements.txt pytest.ini tests/__init__.py trackers/__init__.py setup/__init__.py
git commit -m "chore: scaffold autonomy repo (deps, pytest, package markers)"
```

---

## Task 2: Time utilities (`timeutil.py`)

**Files:**
- Create: `timeutil.py`
- Test: `tests/test_timeutil.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_timeutil.py
from __future__ import annotations
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from timeutil import parse_ts, week_start

def test_parse_ts_handles_z_suffix():
    dt = parse_ts("2026-06-08T13:30:00.000Z")
    assert dt.tzinfo is not None
    assert dt.astimezone(timezone.utc).hour == 13

def test_parse_ts_handles_offset():
    dt = parse_ts("2026-06-08T09:30:00-04:00")
    assert dt.astimezone(timezone.utc).hour == 13

def test_week_start_is_monday_in_local_tz():
    tz = ZoneInfo("America/New_York")
    # 2026-06-10 is a Wednesday; its week starts Monday 2026-06-08
    dt = datetime(2026, 6, 10, 18, 0, tzinfo=timezone.utc)
    assert week_start(dt, tz) == "2026-06-08"

def test_week_start_respects_local_day_boundary():
    tz = ZoneInfo("America/New_York")
    # 2026-06-08 00:30 UTC is still Sunday 2026-06-07 20:30 local -> week of 2026-06-01
    dt = datetime(2026, 6, 8, 0, 30, tzinfo=timezone.utc)
    assert week_start(dt, tz) == "2026-06-01"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/dev/autonomy && python3 -m pytest tests/test_timeutil.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'timeutil'`

- [ ] **Step 3: Write minimal implementation**

```python
# timeutil.py
from __future__ import annotations
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

def parse_ts(s: str) -> datetime:
    """Parse an ISO8601 timestamp (with 'Z' or numeric offset) to a tz-aware datetime."""
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    return datetime.fromisoformat(s)

def week_start(dt: datetime, tz: ZoneInfo) -> str:
    """ISO-date (YYYY-MM-DD) of the Monday that begins dt's week, in local tz."""
    local = dt.astimezone(tz)
    monday = local - timedelta(days=local.weekday())
    return monday.strftime("%Y-%m-%d")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/dev/autonomy && python3 -m pytest tests/test_timeutil.py -q`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
cd ~/dev/autonomy
git add timeutil.py tests/test_timeutil.py
git commit -m "feat: tz-aware timestamp parsing + ISO-week bucketing"
```

---

## Task 3: Session reader — turn classification & tool-action count (`sessions.py`)

This is the load-bearing component (the turn-inflation guard). Build it in two halves: pure per-entry classifiers first (heavily tested), then the file/scope walk.

**Files:**
- Create: `sessions.py`
- Test: `tests/test_sessions.py`, `tests/fixtures/session_basic.jsonl`

- [ ] **Step 1: Write the fixture file**

Create `tests/fixtures/session_basic.jsonl` — one JSON object per line (timestamps all in the week of 2026-06-08):

```json
{"type":"user","cwd":"/Users/me/dev/proj","timestamp":"2026-06-09T14:00:00Z","message":{"role":"user","content":"Refactor the auth module to use the new token store, keep the existing public interface, and add a regression test for the expiry path so we do not lose the fix we just landed."}}
{"type":"user","cwd":"/Users/me/dev/proj","timestamp":"2026-06-09T14:05:00Z","message":{"role":"user","content":"go ahead"}}
{"type":"user","cwd":"/Users/me/dev/proj","timestamp":"2026-06-09T14:06:00Z","message":{"role":"user","content":[{"type":"tool_result","tool_use_id":"x","content":"ok"}]}}
{"type":"user","cwd":"/Users/me/dev/proj","timestamp":"2026-06-09T14:07:00Z","isMeta":true,"message":{"role":"user","content":"meta caveat text"}}
{"type":"user","cwd":"/Users/me/dev/proj","timestamp":"2026-06-09T14:08:00Z","isSidechain":true,"message":{"role":"user","content":"subagent prompt"}}
{"type":"user","cwd":"/Users/me/dev/proj","timestamp":"2026-06-09T14:09:00Z","message":{"role":"user","content":"<command-name>/deploy</command-name>"}}
{"type":"user","cwd":"/Users/me/dev/proj","timestamp":"2026-06-09T14:10:00Z","message":{"role":"user","content":"<local-command-stdout>done</local-command-stdout>"}}
{"type":"user","cwd":"/Users/me/dev/proj","timestamp":"2026-06-09T14:11:00Z","message":{"role":"user","content":"<system-reminder>background note</system-reminder>"}}
{"type":"assistant","cwd":"/Users/me/dev/proj","timestamp":"2026-06-09T14:12:00Z","message":{"role":"assistant","content":[{"type":"text","text":"working"},{"type":"tool_use","id":"a","name":"Bash","input":{}},{"type":"tool_use","id":"b","name":"Read","input":{}}]}}
```

- [ ] **Step 2: Write the failing test (pure classifiers)**

```python
# tests/test_sessions.py
from __future__ import annotations
import json, os
from sessions import classify_user_turn, count_tool_actions

FIX = os.path.join(os.path.dirname(__file__), "fixtures", "session_basic.jsonl")

def _lines():
    with open(FIX) as f:
        return [json.loads(l) for l in f if l.strip()]

def test_classify_spec_and_human_and_drops():
    rows = _lines()
    verdicts = [classify_user_turn(r) for r in rows if r.get("type") == "user"]
    # order matches the fixture's user lines:
    # long brief, "go ahead", tool_result, isMeta, isSidechain, command-name, command-stdout, system-reminder
    assert verdicts == ["spec", "human", "drop", "drop", "drop", "drop", "drop", "drop"]

def test_count_tool_actions_counts_each_tool_use_block():
    rows = _lines()
    assistant = [r for r in rows if r.get("type") == "assistant"][0]
    assert count_tool_actions(assistant) == 2

def test_count_tool_actions_zero_for_user():
    rows = _lines()
    user = [r for r in rows if r.get("type") == "user"][0]
    assert count_tool_actions(user) == 0
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd ~/dev/autonomy && python3 -m pytest tests/test_sessions.py -q`
Expected: FAIL — `ImportError: cannot import name 'classify_user_turn'`

- [ ] **Step 4: Implement the pure classifiers**

```python
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
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd ~/dev/autonomy && python3 -m pytest tests/test_sessions.py -q`
Expected: PASS (3 passed)

- [ ] **Step 6: Write the failing test (scope + aggregation)**

```python
# append to tests/test_sessions.py
from sessions import session_in_scope, aggregate_sessions
from datetime import datetime, timezone

def test_session_in_scope_prefix_match(tmp_path):
    assert session_in_scope("/Users/me/dev/proj/sub", ["/Users/me/dev/proj"]) is True
    assert session_in_scope("/Users/me/dev/other", ["/Users/me/dev/proj"]) is False

def test_aggregate_sessions_buckets_by_week(tmp_path):
    # Point a projects dir at the fixture file inside an encoded-style subdir.
    proj = tmp_path / "-Users-me-dev-proj"
    proj.mkdir()
    (proj / "s.jsonl").write_text(open(FIX).read())
    since = datetime(2026, 6, 1, tzinfo=timezone.utc)
    until = datetime(2026, 6, 15, tzinfo=timezone.utc)
    agg = aggregate_sessions(
        projects_dirs=[str(tmp_path)],
        repo_roots=["/Users/me/dev/proj"],
        tz=ZoneInfo("America/New_York"),
        since=since, until=until, spec_min_chars=160,
    )
    wk = agg["2026-06-08"]
    assert wk["human"] == 1 and wk["spec"] == 1 and wk["actions"] == 2
```

- [ ] **Step 7: Run test to verify it fails**

Run: `cd ~/dev/autonomy && python3 -m pytest tests/test_sessions.py -q`
Expected: FAIL — `ImportError: cannot import name 'session_in_scope'`

- [ ] **Step 8: Implement scope + aggregation**

```python
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
```

- [ ] **Step 9: Run tests to verify they pass**

Run: `cd ~/dev/autonomy && python3 -m pytest tests/test_sessions.py -q`
Expected: PASS (5 passed)

- [ ] **Step 10: Commit**

```bash
cd ~/dev/autonomy
git add sessions.py tests/test_sessions.py tests/fixtures/session_basic.jsonl
git commit -m "feat: session reader — turn classification, scope, weekly aggregation"
```

---

## Task 4: Tracker base — Card, filter, week-bucketing (`trackers/base.py`)

**Files:**
- Create: `trackers/base.py`
- Test: `tests/test_trackers_base.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_trackers_base.py
from __future__ import annotations
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from trackers.base import Card, filter_me, cards_by_week

def _card(title, day, author):
    return Card(id=title, title=title,
                completed_at=datetime(2026, 6, day, 12, 0, tzinfo=timezone.utc),
                author=author)

def test_filter_me_keeps_only_my_cards():
    cards = [_card("a", 9, "me"), _card("b", 9, "someone")]
    assert [c.title for c in filter_me(cards, "me")] == ["a"]

def test_filter_me_none_keeps_all():
    cards = [_card("a", 9, "me"), _card("b", 9, "someone")]
    assert len(filter_me(cards, None)) == 2

def test_cards_by_week_counts_per_monday():
    cards = [_card("a", 9, "me"), _card("b", 10, "me"), _card("c", 2, "me")]
    by = cards_by_week(cards, ZoneInfo("America/New_York"))
    assert by["2026-06-08"] == 2
    assert by["2026-06-01"] == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/dev/autonomy && python3 -m pytest tests/test_trackers_base.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'trackers.base'`

- [ ] **Step 3: Write minimal implementation**

```python
# trackers/base.py
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from zoneinfo import ZoneInfo
from timeutil import week_start

@dataclass
class Card:
    id: str
    title: str
    completed_at: datetime   # tz-aware
    author: str | None       # actor who closed/merged; used by the `me` filter

class Tracker(Protocol):
    def list_completed_cards(self, since: datetime, until: datetime) -> list[Card]: ...

def filter_me(cards: list[Card], me: str | None) -> list[Card]:
    if me is None:
        return list(cards)
    return [c for c in cards if c.author == me]

def cards_by_week(cards: list[Card], tz: ZoneInfo) -> dict[str, int]:
    out: dict[str, int] = {}
    for c in cards:
        wk = week_start(c.completed_at, tz)
        out[wk] = out.get(wk, 0) + 1
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/dev/autonomy && python3 -m pytest tests/test_trackers_base.py -q`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
cd ~/dev/autonomy
git add trackers/base.py tests/test_trackers_base.py
git commit -m "feat: tracker base — Card, me-filter, weekly card counts"
```

---

## Task 5: GitHub Projects adapter (`trackers/github_projects.py`)

Split pure `parse_items` (tested against a recorded fixture) from live `fetch_items` (thin HTTP). Add the `get_tracker` factory.

**Files:**
- Create: `trackers/github_projects.py`
- Modify: `trackers/__init__.py`
- Test: `tests/test_github_projects.py`, `tests/fixtures/github_items.json`

- [ ] **Step 1: Write the fixture**

Create `tests/fixtures/github_items.json` — a trimmed ProjectV2 `items.nodes` array:

```json
[
  {"fieldValueByName": {"name": "Done"},
   "content": {"__typename": "PullRequest", "title": "Merged PR card", "number": 10,
               "merged": true, "mergedAt": "2026-06-09T15:00:00Z",
               "mergedBy": {"login": "me"}, "closedAt": "2026-06-09T15:00:00Z"}},
  {"fieldValueByName": {"name": "Done"},
   "content": {"__typename": "Issue", "title": "Closed issue card", "number": 11,
               "closed": true, "closedAt": "2026-06-10T16:00:00Z",
               "timelineItems": {"nodes": [{"createdAt": "2026-06-10T16:00:00Z",
                                            "actor": {"login": "someone"}}]}}},
  {"fieldValueByName": {"name": "In Progress"},
   "content": {"__typename": "Issue", "title": "Not done", "number": 12,
               "closed": false, "closedAt": null,
               "timelineItems": {"nodes": []}}},
  {"fieldValueByName": null, "content": null}
]
```

- [ ] **Step 2: Write the failing test**

```python
# tests/test_github_projects.py
from __future__ import annotations
import json, os
from datetime import datetime, timezone
from trackers.github_projects import parse_items

FIX = os.path.join(os.path.dirname(__file__), "fixtures", "github_items.json")
SINCE = datetime(2026, 6, 1, tzinfo=timezone.utc)
UNTIL = datetime(2026, 6, 15, tzinfo=timezone.utc)

def test_parse_items_picks_done_cards_only():
    nodes = json.load(open(FIX))
    cards = parse_items(nodes, done_status=["Done"], since=SINCE, until=UNTIL, me=None)
    titles = sorted(c.title for c in cards)
    assert titles == ["Closed issue card", "Merged PR card"]

def test_parse_items_sets_author_and_completed_at():
    nodes = json.load(open(FIX))
    cards = {c.title: c for c in parse_items(nodes, ["Done"], SINCE, UNTIL, None)}
    assert cards["Merged PR card"].author == "me"
    assert cards["Merged PR card"].completed_at == datetime(2026, 6, 9, 15, 0, tzinfo=timezone.utc)
    assert cards["Closed issue card"].author == "someone"

def test_parse_items_me_filter():
    nodes = json.load(open(FIX))
    cards = parse_items(nodes, ["Done"], SINCE, UNTIL, me="me")
    assert [c.title for c in cards] == ["Merged PR card"]

def test_parse_items_window_excludes_outside():
    nodes = json.load(open(FIX))
    cards = parse_items(nodes, ["Done"], SINCE, datetime(2026, 6, 9, 20, 0, tzinfo=timezone.utc), None)
    assert [c.title for c in cards] == ["Merged PR card"]  # issue closed 6/10 is now outside
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd ~/dev/autonomy && python3 -m pytest tests/test_github_projects.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'trackers.github_projects'`

- [ ] **Step 4: Implement parse + fetch**

```python
# trackers/github_projects.py
from __future__ import annotations
import os
from datetime import datetime
import requests
from timeutil import parse_ts
from trackers.base import Card, filter_me

GQL_URL = "https://api.github.com/graphql"

_QUERY = """
query($project: ID!, $cursor: String) {
  node(id: $project) {
    ... on ProjectV2 {
      items(first: 100, after: $cursor) {
        pageInfo { hasNextPage endCursor }
        nodes {
          fieldValueByName(name: "Status") {
            ... on ProjectV2ItemFieldSingleSelectValue { name }
          }
          content {
            __typename
            ... on Issue {
              title number closed closedAt
              timelineItems(first: 1, itemTypes: CLOSED_EVENT) {
                nodes { ... on ClosedEvent { createdAt actor { login } } }
              }
            }
            ... on PullRequest {
              title number merged mergedAt closedAt mergedBy { login }
            }
          }
        }
      }
    }
  }
}
"""

def _status_name(node: dict) -> str | None:
    fv = node.get("fieldValueByName") or {}
    return fv.get("name")

def _completion(content: dict) -> tuple[datetime | None, str | None]:
    """(earliest completion ts, author) or (None, None) if not completed."""
    candidates: list[tuple[datetime, str | None]] = []
    if content.get("__typename") == "PullRequest" and content.get("merged"):
        if content.get("mergedAt"):
            login = (content.get("mergedBy") or {}).get("login")
            candidates.append((parse_ts(content["mergedAt"]), login))
    if content.get("__typename") == "Issue" and content.get("closed"):
        tl = (content.get("timelineItems") or {}).get("nodes") or []
        if tl and tl[0].get("createdAt"):
            login = (tl[0].get("actor") or {}).get("login")
            candidates.append((parse_ts(tl[0]["createdAt"]), login))
        elif content.get("closedAt"):
            candidates.append((parse_ts(content["closedAt"]), None))
    if not candidates:
        return None, None
    return min(candidates, key=lambda t: t[0])

def parse_items(nodes: list[dict], done_status: list[str], since: datetime,
                until: datetime, me: str | None) -> list[Card]:
    cards: list[Card] = []
    done_set = set(done_status)
    for node in nodes:
        content = node.get("content")
        if not content:
            continue
        status = _status_name(node)
        ts, author = _completion(content)
        is_done = (status in done_set) or (ts is not None)
        if not is_done or ts is None:
            continue
        if not (since <= ts <= until):
            continue
        cards.append(Card(id=str(content.get("number", content.get("title"))),
                          title=content.get("title", ""),
                          completed_at=ts, author=author))
    return filter_me(cards, me)

def fetch_items(token: str, project_node_id: str) -> list[dict]:
    nodes: list[dict] = []
    cursor = None
    headers = {"Authorization": f"Bearer {token}"}
    while True:
        resp = requests.post(GQL_URL, headers=headers,
                             json={"query": _QUERY,
                                   "variables": {"project": project_node_id, "cursor": cursor}})
        resp.raise_for_status()
        data = resp.json()
        if "errors" in data:
            raise RuntimeError(f"GitHub GraphQL error: {data['errors']}")
        items = data["data"]["node"]["items"]
        nodes.extend(items["nodes"])
        if not items["pageInfo"]["hasNextPage"]:
            return nodes
        cursor = items["pageInfo"]["endCursor"]

class GitHubProjectsTracker:
    def __init__(self, token: str, project_node_id: str, done_status: list[str], me: str | None):
        self._token = token
        self._project = project_node_id
        self._done = done_status
        self._me = me

    def list_completed_cards(self, since: datetime, until: datetime) -> list[Card]:
        nodes = fetch_items(self._token, self._project)
        return parse_items(nodes, self._done, since, until, self._me)
```

- [ ] **Step 5: Add the factory to `trackers/__init__.py`**

```python
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
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd ~/dev/autonomy && python3 -m pytest tests/test_github_projects.py -q`
Expected: PASS (4 passed)

- [ ] **Step 7: Commit**

```bash
cd ~/dev/autonomy
git add trackers/github_projects.py trackers/__init__.py tests/test_github_projects.py tests/fixtures/github_items.json
git commit -m "feat: GitHub Projects tracker adapter + get_tracker factory"
```

---

## Task 6: Linear adapter (`trackers/linear.py`)

**Files:**
- Create: `trackers/linear.py`
- Test: `tests/test_linear.py`, `tests/fixtures/linear_issues.json`

- [ ] **Step 1: Write the fixture**

Create `tests/fixtures/linear_issues.json` — a trimmed Linear `issues.nodes` array:

```json
[
  {"identifier": "BRI-1", "title": "Completed assigned", "completedAt": "2026-06-09T15:00:00Z",
   "state": {"type": "completed"}, "assignee": {"email": "brian@example.com"},
   "creator": {"email": "brian@example.com"}},
  {"identifier": "BRI-2", "title": "Completed unassigned", "completedAt": "2026-06-10T16:00:00Z",
   "state": {"type": "completed"}, "assignee": null,
   "creator": {"email": "someone@example.com"}},
  {"identifier": "BRI-3", "title": "Still started", "completedAt": null,
   "state": {"type": "started"}, "assignee": {"email": "brian@example.com"},
   "creator": {"email": "brian@example.com"}}
]
```

- [ ] **Step 2: Write the failing test**

```python
# tests/test_linear.py
from __future__ import annotations
import json, os
from datetime import datetime, timezone
from trackers.linear import parse_issues

FIX = os.path.join(os.path.dirname(__file__), "fixtures", "linear_issues.json")
SINCE = datetime(2026, 6, 1, tzinfo=timezone.utc)
UNTIL = datetime(2026, 6, 15, tzinfo=timezone.utc)

def test_parse_issues_completed_only():
    nodes = json.load(open(FIX))
    cards = sorted(c.title for c in parse_issues(nodes, SINCE, UNTIL, None))
    assert cards == ["Completed assigned", "Completed unassigned"]

def test_parse_issues_author_is_assignee_else_creator():
    nodes = json.load(open(FIX))
    by = {c.title: c for c in parse_issues(nodes, SINCE, UNTIL, None)}
    assert by["Completed assigned"].author == "brian@example.com"
    assert by["Completed unassigned"].author == "someone@example.com"  # falls back to creator

def test_parse_issues_me_filter():
    nodes = json.load(open(FIX))
    cards = parse_issues(nodes, SINCE, UNTIL, me="brian@example.com")
    assert [c.title for c in cards] == ["Completed assigned"]
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd ~/dev/autonomy && python3 -m pytest tests/test_linear.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'trackers.linear'`

- [ ] **Step 4: Implement parse + fetch**

```python
# trackers/linear.py
from __future__ import annotations
from datetime import datetime
import requests
from timeutil import parse_ts
from trackers.base import Card, filter_me

GQL_URL = "https://api.linear.app/graphql"

_QUERY = """
query($team: ID!, $cursor: String) {
  team(id: $team) {
    issues(first: 100, after: $cursor,
           filter: { state: { type: { eq: "completed" } } }) {
      pageInfo { hasNextPage endCursor }
      nodes {
        identifier title completedAt
        state { type }
        assignee { email }
        creator { email }
      }
    }
  }
}
"""

def parse_issues(nodes: list[dict], since: datetime, until: datetime,
                 me: str | None) -> list[Card]:
    cards: list[Card] = []
    for n in nodes:
        if (n.get("state") or {}).get("type") != "completed":
            continue
        if not n.get("completedAt"):
            continue
        ts = parse_ts(n["completedAt"])
        if not (since <= ts <= until):
            continue
        author = (n.get("assignee") or {}).get("email") or (n.get("creator") or {}).get("email")
        cards.append(Card(id=n.get("identifier", n.get("title", "")),
                          title=n.get("title", ""), completed_at=ts, author=author))
    return filter_me(cards, me)

def fetch_issues(token: str, team_id: str) -> list[dict]:
    nodes: list[dict] = []
    cursor = None
    headers = {"Authorization": token}  # Linear uses the raw key, no "Bearer "
    while True:
        resp = requests.post(GQL_URL, headers=headers,
                             json={"query": _QUERY, "variables": {"team": team_id, "cursor": cursor}})
        resp.raise_for_status()
        data = resp.json()
        if "errors" in data:
            raise RuntimeError(f"Linear GraphQL error: {data['errors']}")
        issues = data["data"]["team"]["issues"]
        nodes.extend(issues["nodes"])
        if not issues["pageInfo"]["hasNextPage"]:
            return nodes
        cursor = issues["pageInfo"]["endCursor"]

class LinearTracker:
    def __init__(self, token: str, team_id: str, me: str | None):
        self._token = token
        self._team = team_id
        self._me = me

    def list_completed_cards(self, since: datetime, until: datetime) -> list[Card]:
        nodes = fetch_issues(self._token, self._team)
        return parse_issues(nodes, since, until, self._me)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd ~/dev/autonomy && python3 -m pytest tests/test_linear.py -q`
Expected: PASS (3 passed)

- [ ] **Step 6: Commit**

```bash
cd ~/dev/autonomy
git add trackers/linear.py tests/test_linear.py tests/fixtures/linear_issues.json
git commit -m "feat: Linear tracker adapter"
```

---

## Task 7: Metrics join (`metrics.py`)

**Files:**
- Create: `metrics.py`
- Test: `tests/test_metrics.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_metrics.py
from __future__ import annotations
from metrics import build_rows, Row

def test_build_rows_joins_and_computes():
    cards = {"2026-06-08": 16, "2026-06-01": 41}
    sessions = {"2026-06-08": {"human": 222, "spec": 72, "actions": 6860},
                "2026-06-01": {"human": 337, "spec": 108, "actions": 9840}}
    rows = build_rows(cards, sessions)
    r = {row.week: row for row in rows}
    assert r["2026-06-08"].cards == 16
    assert r["2026-06-08"].spec_per_card == 4.5
    assert round(r["2026-06-08"].actions_per_steer, 1) == 30.9
    # rows are sorted ascending by week
    assert [row.week for row in rows] == ["2026-06-01", "2026-06-08"]

def test_build_rows_zero_cards_yields_none_ratios():
    cards = {}  # a week with sessions but no completed cards
    sessions = {"2026-06-08": {"human": 10, "spec": 2, "actions": 50}}
    rows = build_rows(cards, sessions)
    assert rows[0].cards == 0
    assert rows[0].spec_per_card is None          # no divide-by-zero
    assert round(rows[0].actions_per_steer, 1) == 5.0

def test_build_rows_zero_human_yields_none_actions_per_steer():
    rows = build_rows({"2026-06-08": 3}, {"2026-06-08": {"human": 0, "spec": 0, "actions": 0}})
    assert rows[0].actions_per_steer is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/dev/autonomy && python3 -m pytest tests/test_metrics.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'metrics'`

- [ ] **Step 3: Write minimal implementation**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/dev/autonomy && python3 -m pytest tests/test_metrics.py -q`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
cd ~/dev/autonomy
git add metrics.py tests/test_metrics.py
git commit -m "feat: metrics join — 5 columns, safe ratios for zero-denominator weeks"
```

---

## Task 8: Report rendering (`report.py`)

**Files:**
- Create: `report.py`
- Test: `tests/test_report.py`

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/dev/autonomy && python3 -m pytest tests/test_report.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'report'`

- [ ] **Step 3: Write minimal implementation**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/dev/autonomy && python3 -m pytest tests/test_report.py -q`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
cd ~/dev/autonomy
git add report.py tests/test_report.py
git commit -m "feat: report rendering — stdout table, CSV, Markdown"
```

---

## Task 9: Config loader (`config.py`)

**Files:**
- Create: `config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/dev/autonomy && python3 -m pytest tests/test_config.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'config'`

- [ ] **Step 3: Write minimal implementation**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/dev/autonomy && python3 -m pytest tests/test_config.py -q`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
cd ~/dev/autonomy
git add config.py tests/test_config.py
git commit -m "feat: config loader — validation + defaults"
```

---

## Task 10: CLI entrypoint (`autonomy.py`)

Wire config → tracker → sessions → metrics → report. The window math and DI seam are tested; the live wiring is exercised by a monkeypatched smoke.

**Files:**
- Create: `autonomy.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli.py
from __future__ import annotations
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import autonomy as cli

def test_window_weeks_spans_back_from_until():
    until = datetime(2026, 6, 12, 12, 0, tzinfo=timezone.utc)
    since, end = cli.window(weeks=2, since=None, now=until)
    assert end == until
    assert (until - since).days == 14

def test_window_explicit_since_overrides_weeks():
    until = datetime(2026, 6, 12, tzinfo=timezone.utc)
    since, end = cli.window(weeks=6, since="2026-05-01", now=until)
    assert since == datetime(2026, 5, 1, tzinfo=timezone.utc)

def test_build_footer_mentions_scope_and_tracker():
    cfg = {"tracker": {"type": "github_projects", "me": "davidmshaner-gi"}}
    f = cli.build_footer(cfg)
    assert "upper bound" in f and "github_projects" in f and "davidmshaner-gi" in f
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/dev/autonomy && python3 -m pytest tests/test_cli.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'autonomy'`

- [ ] **Step 3: Write minimal implementation**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/dev/autonomy && python3 -m pytest tests/test_cli.py -q`
Expected: PASS (3 passed)

- [ ] **Step 5: Full suite green + import smoke**

Run: `cd ~/dev/autonomy && python3 -m pytest -q && python3 -c "import autonomy; print('cli ok')"`
Expected: all tests PASS; prints `cli ok`

- [ ] **Step 6: Commit**

```bash
cd ~/dev/autonomy
git add autonomy.py tests/test_cli.py
git commit -m "feat: CLI entrypoint wiring config -> tracker -> sessions -> metrics -> report"
```

---

## Task 11: Machine discovery (`setup/discover.py`)

**Files:**
- Create: `setup/discover.py`
- Test: `tests/test_discover.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_discover.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/dev/autonomy && python3 -m pytest tests/test_discover.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'setup.discover'`

- [ ] **Step 3: Write minimal implementation**

```python
# setup/discover.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/dev/autonomy && python3 -m pytest tests/test_discover.py -q`
Expected: PASS (1 passed)

- [ ] **Step 5: Real-machine smoke**

Run: `cd ~/dev/autonomy && python3 setup/discover.py | python3 -c "import json,sys; d=json.load(sys.stdin); print('roots:', len(d['candidate_roots']), 'cc_exists:', d['projects_dir_exists'])"`
Expected: prints a nonzero root count and `cc_exists: True` on David's machine.

- [ ] **Step 6: Commit**

```bash
cd ~/dev/autonomy
git add setup/discover.py tests/test_discover.py
git commit -m "feat: machine discovery for setup (ranked work roots, JSONL dirs)"
```

---

## Task 12: Docs, example config, setup skill, README, and publish

No tests (docs + publish). **G8 lives here.**

**Files:**
- Create: `config.example.yaml`, `setup/SKILL.md`, `README.md`

- [ ] **Step 1: Write `config.example.yaml`**

```yaml
# autonomy config. Copy to config.yaml (gitignored) and edit. Relative paths
# resolve against $HOME; ~ expands.
timezone: America/New_York
week_start: monday

# Where Claude Code session JSONL lives (yours may differ).
projects_dirs:
  - .claude/projects
# cowork_root: Library/Application Support/Claude/local-agent-mode-sessions   # optional

# Sessions whose working dir is under one of these roots count toward this
# project's cards (repo-scoped UPPER BOUND — see README).
scope:
  repo_roots:
    - ~/dev/your-project

tracker:
  type: github_projects            # github_projects | linear
  token_env: AUTONOMY_TRACKER_TOKEN # name of the env var holding your API token
  # --- github_projects ---
  project_node_id: PVT_xxxxxxxx     # GraphQL node id of your ProjectV2 board
  done_status: [Done]               # Status field option(s) that mean "complete"
  me: your-github-login             # optional; omit to count all cards
  # --- linear (set type: linear and use these instead) ---
  # team_id: TEAM_xxxxxxxx
  # me: you@example.com

spec_turn_min_chars: 160            # human turns >= this length count as "spec turns"
```

- [ ] **Step 2: Write `setup/SKILL.md`**

```markdown
---
name: autonomy-setup
description: Set up the autonomy meter on this machine — discover JSONL paths, pick a card tracker (GitHub Projects or Linear), write config, and run the first weekly report.
---

# Autonomy Setup

You are setting up `autonomy` for the user on THIS machine. It reads their card
tracker + Claude Code session logs and prints weekly agent-autonomy metrics.
Follow these steps in order.

## 1. Discover the machine
Run `python3 setup/discover.py` and read the JSON: OS, the Claude Code projects
dir (and whether it exists), the Cowork dir, and candidate work roots ranked by
session count. If `projects_dir_exists` is false, stop — autonomy needs Claude
Code session history.

## 2. Pick the tracker
Ask: GitHub Projects or Linear?
- **GitHub Projects:** ask for the ProjectV2 node id (`gh api graphql` or the
  board URL → node id), the Status option(s) that mean done (default `[Done]`),
  and their GitHub login (optional `me` filter). Token: a PAT with `project`
  scope.
- **Linear:** ask for the team id and their Linear email (optional `me`). Token:
  a Linear personal API key.
Have them put the token in an env var and record the var NAME (not the value) as
`token_env`. Never write the token into config.

## 3. Pick the scope roots
Show the top candidate roots (decoded path + session count). Ask which one(s)
are this project's repo — those become `scope.repo_roots`. Everything under them
counts as work that produced these cards (an upper bound).

## 4. Write config.yaml
Copy `config.example.yaml` → `config.yaml`. Set `timezone` (infer from system or
ask), `projects_dirs` (from discovery), the tracker block, and `scope.repo_roots`.

## 5. First report
Run `python3 autonomy.py --weeks 6` and show the table. If a week shows `—` for
ratios, that week had zero cards (or zero human turns) — expected, not a bug.
```

- [ ] **Step 3: Write `README.md`**

```markdown
# autonomy

A weekly agent-autonomy meter. Point it at your card tracker (GitHub Projects or
Linear) and your Claude Code session logs; it prints how much *steering* each
shipped card costs and how much the model does per steer.

| column | meaning |
|---|---|
| cards | completed cards that week |
| human turns | genuine steering messages (tool results, meta, sidechains, and harness injections excluded) |
| spec turns | human turns ≥ `spec_turn_min_chars` (real briefs, not "go ahead") |
| spec/card | steering effort per shipped card — falling = more autonomy |
| actions/steer | model tool-actions per human turn — rising = model doing more per nudge |

Scope is a **repo-root upper bound**: every session whose working dir is under
`scope.repo_roots` counts toward that project's cards. It does not link specific
sessions to specific cards.

## Setup (with Claude Code)
Clone, open in Claude Code, and paste:
> Read `setup/SKILL.md` and set up autonomy for me.

## Manual setup
1. `pip3 install -r requirements.txt`
2. `cp config.example.yaml config.yaml` and edit it.
3. `export AUTONOMY_TRACKER_TOKEN=<your token>` (the env var named in `config.yaml`).
4. `python3 autonomy.py --weeks 6`

## Usage
```
python3 autonomy.py --weeks 6
python3 autonomy.py --since 2026-05-01 --csv out.csv --md out.md
```

## How it works
Deterministic, no LLM: tracker adapter → session reader → weekly join → report.
Adding a tracker = one file implementing `Tracker.list_completed_cards`.
```

- [ ] **Step 4: Commit the docs**

```bash
cd ~/dev/autonomy
git add config.example.yaml setup/SKILL.md README.md
git commit -m "docs: example config, setup skill, README"
```

- [ ] **Step 5: Create the GitHub repo and push (G8)**

> **G8 — account resolution.** This repo is owned by the **`davidmshaner`** account (default per root CLAUDE.md). A `Repository not found` error means the WRONG ACCOUNT is active, never a missing repo — switch accounts and retry before concluding anything.

```bash
cd ~/dev/autonomy
gh auth switch --user davidmshaner          # ensure the owning account is active
gh auth status                               # confirm davidmshaner is active
gh repo create davidmshaner/autonomy --public --source=. --remote=origin --push
```

If `gh repo create` reports the repo already exists or `Repository not found`, do NOT conclude the repo is missing — verify the active account is `davidmshaner` (`gh auth status`), switch if needed (`gh auth switch --user davidmshaner`), and retry. After a successful push, the default account is already `davidmshaner`, so no switch-back is needed.

- [ ] **Step 6: Verify the push**

Run: `gh repo view davidmshaner/autonomy --json name,visibility,defaultBranchRef -q '.name + " " + .visibility'`
Expected: `autonomy PUBLIC`

---

## Self-Review (completed by plan author)

**Spec coverage:** Every spec section maps to a task — metrics (Tasks 3,7,8), turn-classification rules (Task 3), tracker interface + both adapters (Tasks 4,5,6), config shape (Tasks 9,12), repo-root scoping (Task 3), report-only output stdout/CSV/MD (Task 8), CLI (Task 10), setup skill + discovery (Tasks 10... 11,12), distribution/public repo (Task 12), Python 3.9 `from __future__ import annotations` (every module). Non-goals respected: no Sheet/publisher, no session↔card linking, no minutes, no LLM.

**Placeholder scan:** No TBD/TODO; every code step shows complete code; every command shows expected output.

**Type consistency:** `Card(id,title,completed_at,author)` used identically in Tasks 4/5/6. `aggregate_sessions(...)` signature matches its call in Task 10. `build_rows(cards_by_week, sessions_by_week)` returns `Row` used in Task 8. `Row` fields (`week,cards,human,spec,spec_per_card,actions_per_steer`) consistent across Tasks 7/8/10. `get_tracker(cfg["tracker"])` consumes the validated tracker block from Task 9. `render_table/csv/markdown` signatures match their Task 10 calls.
