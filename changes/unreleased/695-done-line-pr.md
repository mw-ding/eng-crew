---
type: fixed
issue: 695
pr: TBD
date: 2026-11-03
box-skill: none (tmux only)
---

`crew kill` and idle-builder reclaim no longer report a squash-merged builder worktree as unlanded when the builder's `done: #<issue> #<pr> <sha>` line carries a trailing note. The PR number is now read from a done line with text after the SHA, so the `pull/<n>/head` commits count as landed after the branch is deleted.
