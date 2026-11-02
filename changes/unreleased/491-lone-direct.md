---
type: changed
issue: 491
pr: 498
date: 2026-11-01
box-skill: deferred to #140
---

Add the tmux lone_pr_land profile option: direct lands a single ready PR without a default-branch catch-up, records the gate waiver and checks merge-commit CI; a red default branch triggers a blocking coordinator fix issue. The default train policy and all other merge gates remain required.
