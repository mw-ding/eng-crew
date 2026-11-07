---
type: fixed
issue: 1250
pr: TBD
date: 2026-11-07
box-skill: none
---

`scripts/worktree-purge.py` now keeps a worktree whose path sits inside a path referenced by a run record, claim or tmux pane, with the reason `inside a referenced run`. Before, the guard matched only the exact path, so a nested worktree such as a live builder's `.crew/base` snapshot was classified `remove` and `--apply` would have deleted it. Worktrees under a protected checkout were already kept.
