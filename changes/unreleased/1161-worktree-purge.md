---
type: added
issue: 1161
pr: 1164
date: 2026-11-06
box-skill: none
---

`scripts/worktree-purge.py` is a one-off purge of stale git worktrees on the crew host, an early slice of #316. It lists every worktree of the repo with branch, head, PR state read back from GitHub, a `keep` or `remove` classification and the reason, and is a dry run by default. A row is `remove` only when it is not the main worktree, a protected checkout or the current directory; no run record, claim or tmux pane references it; `git status` is clean apart from `.crew/` scratch; and its head is in `origin/main`, or a merged or closed PR has exactly that head and its remote branch matches or is gone. `--apply` runs `git worktree remove` without `--force` on `remove` rows only, then `git worktree prune`, and leaves local branches alone.
