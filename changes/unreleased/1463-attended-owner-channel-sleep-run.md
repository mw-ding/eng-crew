---
type: added
issue: 1463
pr: 1471
date: 2026-11-08
box-skill: none
---

`scripts/campaign-attended.py` drives #804's attended run: A26 around an actual sleep of the owner's Mac, with one real sandbox Slack delivery whose receipt code the owner types after the wake. It records the before-sleep and after-resume timestamps, checks that claims, worktrees and tmux windows survive the sleep, runs A26's resume steps (missed changes and the overdue sweep caught up once) and records each owner unblock. `--dry-run` rehearses end to end with a loopback webhook and no sleep, labelled `rehearsal` and `evidence: false`. `docs/campaign-harness.md` gains the runbook: the owner's steps and timing, and the physical test boundary. A26's watcher ticks pass `--source-interval 0`, so its resume scan polls again within the 60 s source interval that #1300 added.
