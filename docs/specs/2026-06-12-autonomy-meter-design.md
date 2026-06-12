# Autonomy — an agent-autonomy meter

**Status:** Design approved 2026-06-12
**Repo:** `davidmshaner/autonomy` (public) — lives at `~/dev/autonomy`
**Sibling to:** Pulse (`~/dev/pulse`) — same self-contained, config-driven, Claude-Code-self-setup shape

## Problem

When you ship work with a coding agent, the felt signal of "the model is doing
more on its own" has no number behind it. You notice fewer human-in-the-loop
turns per shipped card, but "fewer turns" is fuzzy and easy to inflate (saying
"yes" 40 times is not 40 specs).

`autonomy` turns that felt signal into a weekly table: how much *steering* each
shipped card costs, and how much the model does per steer. Point it at a card
tracker (GitHub Projects or Linear) and your Claude Code session logs; it prints
the trend.

This generalizes a one-off measurement built for the GI "Plugin Development
Pipeline" board so a second user (Brian — Linear + Claude Code, JSONL possibly in
a different location) can run it on his own setup.

## Non-goals (YAGNI)

- **No external write surface.** Report-only: stdout + CSV + Markdown. No Google
  Sheet, no writing back to the tracker. (David's GI Sheet stays a separate
  one-off; GI issue #21 is unaffected by this tool.)
- **No session-to-card linking.** Sessions are scoped to repo roots as an
  upper bound, honestly labeled in output. No branch-name / commit-id attribution.
- **No time/minutes.** Pulse owns hours. `autonomy` does not depend on Pulse and
  does not compute durations — Brian does not need Pulse installed.
- **No LLM in the path.** Fully deterministic, like Pulse.

## Metrics (fixed product opinion)

The five columns, per ISO week:

| column | definition |
|---|---|
| `cards` | completed cards that week, from the tracker. Optional `me` filter counts only cards you authored/closed. |
| `human turns` | genuine steering messages. A user JSONL entry counts **unless** it is a `tool_result`, `isMeta`, `isSidechain`, command-output (`<command-name>` / `<local-command-stdout>`), or a harness injection (`<skill_md>`, `<task-notification>`, `<system-reminder>`, slash-command stdout, and similar wrapper markers). |
| `spec turns` | human turns whose text length ≥ `spec_turn_min_chars` (default 160). Substantive briefs/specs, not "go ahead". |
| `spec/card` | `spec turns ÷ cards`. **Falling = more autonomy** (less steering per shipped card). |
| `actions/steer` | assistant tool-use actions ÷ `human turns`. **Rising = model doing more per nudge.** A tool-use action = one `tool_use` block in an assistant message (parallel tool calls count individually; subagent fan-out inflates this and that is expected/desirable). |

`spec_turn_min_chars` is the only tunable knob. Everything else is fixed so the
numbers mean the same thing across users.

### Turn-classification rules (the load-bearing detail)

This is where the earlier one-off first went wrong (454 inflated turns). The
reader walks each session JSONL line and applies, in order:

1. Only `type == "user"` (or role user) entries are turn candidates. Assistant
   and system lines are never human turns.
2. Drop if the entry is a `tool_result` (content is a `tool_result` block, or
   `message.content[].type == "tool_result"`).
3. Drop if `isMeta == true`.
4. Drop if `isSidechain == true` (subagent transcripts).
5. Drop if the text body is wrapped in a harness/command marker:
   `<command-name>`, `<command-message>`, `<command-args>`,
   `<local-command-stdout>`, `<local-command-caveat>`, `<skill_md>`,
   `<task-notification>`, `<system-reminder>`, `<bash-stdout>`/`<bash-stderr>`,
   or is purely such injected content.
6. What survives is a **genuine human turn**. If its text length ≥ threshold,
   it is also a **spec turn**.

These rules live in one place (`sessions.py`) and are covered by fixture tests so
the definition can't silently drift.

## Architecture

Deterministic pipeline, same spirit as Pulse:

```
cards (tracker adapter) ─┐
                          ├─> metrics (join by ISO week) ─> report (stdout/CSV/MD)
sessions (JSONL reader) ─┘
```

### Layout

```
autonomy/
  config.example.yaml      # the only thing a new user edits (copied -> config.yaml, gitignored)
  config.py                # load + validate + path-resolve config
  trackers/
    base.py                # Card dataclass + Tracker interface
    github_projects.py     # GraphQL adapter (reuses the GI board query)
    linear.py              # Linear GraphQL adapter
  sessions.py              # walk JSONL under projects_dirs, window + repo-root scope,
                           #   classify turns, count tool-use actions -> weekly aggregates
  metrics.py               # join cards x sessions by ISO week -> rows of the 5 columns
  report.py                # render rows -> stdout table + CSV + Markdown (+ upper-bound footer)
  autonomy.py              # CLI entrypoint
  setup/
    SKILL.md               # Claude Code self-configures it (mirrors pulse-setup)
    discover.py            # finds JSONL dirs + candidate work roots, prints JSON
  tests/
    test_sessions.py       # turn-classification fixtures (incl. the inflation traps)
    test_metrics.py        # week-join + division math, zero-card weeks
  README.md
  .gitignore               # config.yaml, __pycache__, .cache
```

### Tracker adapter interface

The whole abstraction. `trackers/base.py`:

```python
@dataclass
class Card:
    id: str
    title: str
    completed_at: datetime   # tz-aware
    author: str | None       # actor who closed/merged, for the `me` filter

class Tracker(Protocol):
    def list_completed_cards(self, since: datetime, until: datetime) -> list[Card]: ...
```

"Completed" is tracker-defined:

- **github_projects** — a card is complete when its Status field is in
  `done_status` (default `[Done]`) **or** its linked PR is merged. Completion
  timestamp = the Status-change / `mergedAt` / `closedAt`. `author` = merger /
  closing actor. Needs a PAT with `project` scope + the project node id.
  (Reuses the GraphQL already written for `PVT_kwHOD0wr8c4BZEma`.) A card
  counts **once** — if both signals fire, completion = the earliest of them.
- **linear** — a card is complete when its workflow state has `type ==
  "completed"`. Completion timestamp = `completedAt`. `author` = assignee (or
  creator if unassigned). Needs a Linear API key + team id.

Optional `me` config filters to cards whose `author` matches (David excludes
Bonner this way; Brian solo can omit it to count everything).

Credentials come from an **env var named in config** (`token_env`), never the
repo. Adding a third tracker later = one new file implementing `Tracker`.

### Session reader

`sessions.py` walks each path in `projects_dirs` (Claude Code) and optional
`cowork_root`, reads JSONL, and keeps only sessions whose working directory
resolves under one of `scope.repo_roots`. The cwd is recovered from the session's
encoded project-dir slug (the `-Users-...` directory name) decoded back to a
filesystem path, matched as a prefix against `repo_roots`. For each kept session
it emits, bucketed by the ISO week of each message's timestamp:

- genuine human turns (rules above)
- spec turns
- assistant tool-use action count

### Config

`config.example.yaml`:

```yaml
timezone: America/New_York
week_start: monday

# Where Claude Code session JSONL lives (Brian's may differ).
projects_dirs:
  - .claude/projects
# cowork_root: Library/Application Support/Claude/local-agent-mode-sessions   # optional

# Sessions whose working dir is under one of these roots count toward this
# project's cards (repo-scoped UPPER BOUND).
scope:
  repo_roots:
    - ~/dev/chief_of_staff/projects/shaner_consulting_llc/clients/active/grounded_intelligence

tracker:
  type: github_projects            # github_projects | linear
  token_env: AUTONOMY_TRACKER_TOKEN
  # --- github_projects ---
  project_node_id: PVT_kwHOD0wr8c4BZEma
  done_status: [Done]
  me: davidmshaner-gi              # optional; omit to count all cards
  # --- linear (when type: linear) ---
  # team_id: TEAM_xxxxx
  # me: brian@example.com

spec_turn_min_chars: 160
```

Relative paths resolve against `$HOME`; `~` expands. `config.py` validates the
tracker block against its `type` and fails with a legible message (not a
traceback) on missing creds/ids.

### CLI

```
python autonomy.py --weeks 6                 # last 6 ISO weeks, stdout table
python autonomy.py --since 2026-05-01        # explicit window
python autonomy.py --weeks 6 --csv out.csv --md out.md
```

Default with no args: last 6 weeks to stdout. Output always ends with a footer:
`scope: repo-root upper bound (N sessions, M cards) — see docs`.

### Output shape (stdout)

```
week of      cards  human turns  spec turns  spec/card  actions/steer
2026-05-25      16          222          72       4.50           30.9
2026-06-01      41          337         108       2.63           29.2
2026-06-08      36          256          58       1.61           79.2
scope: repo-root upper bound · github_projects · me=davidmshaner-gi
```

## Setup (Claude Code self-config, mirrors pulse-setup)

`setup/SKILL.md` drives a fresh-machine setup:

1. `python setup/discover.py` → JSON: OS, Claude Code projects dir (exists?),
   Cowork dir (exists?), candidate work roots ranked by session count.
2. Interview: which tracker (GitHub Projects / Linear), its ids, the env var
   holding the token, optional `me`.
3. Interview: which discovered work root(s) are this project's `repo_roots`.
4. Write `config.yaml` (timezone inferred or asked; `projects_dirs` from
   discovery).
5. Run `python autonomy.py --weeks 6` and show the first table.

Manual setup path documented in README for non-Claude-Code users (`pip install
pyyaml requests`, copy + edit `config.yaml`, set the token env var, run).

## Testing

- `test_sessions.py` — fixture JSONL lines for every drop rule (tool_result,
  isMeta, isSidechain, each harness marker, command-output) plus genuine turns
  and a spec-threshold boundary case. Asserts counts match. This is the
  regression guard against turn inflation.
- `test_metrics.py` — week join, integer/zero-card weeks (no divide-by-zero;
  `spec/card` and `actions/steer` render `—` when denominator is 0), tz handling
  at week boundaries.

## Distribution

New public GitHub repo `davidmshaner/autonomy`. No secrets in-repo (tokens via
the env var named in `config.yaml`; `config.yaml` is gitignored). Brian clones,
opens in Claude Code, pastes *"Read `setup/SKILL.md` and set up autonomy for
me"*, and gets his first Linear-backed table.

## Open questions

None blocking. Future (out of scope for v1): publishers (push the table to a
Sheet / Slack), session↔card linking for a tighter bound, a `--me-only` flag
override.
