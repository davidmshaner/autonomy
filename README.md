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
