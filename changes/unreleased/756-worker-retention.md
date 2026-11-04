---
type: fixed
issue: 756
pr: 829
date: 2026-11-04
box-skill: none (docs-only)
---

`docs/roles.md` no longer describes every worker as fire-and-forget. Roles
keeps the isolation constraint (one unique worktree per run, never delete
another run's tree or unlanded work) and now defers retention and safe
reclaim to the runtime binding, linking contract C6 and the tmux Q2,
`crew dequeue` and `crew kill` sections. No gate change.
