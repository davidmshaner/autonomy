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
