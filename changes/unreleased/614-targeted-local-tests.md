---
type: changed
issue: 614
pr: TBD
date: 2026-11-03
box-skill: pending coordinator mirror
---

Builders run a targeted local test set instead of the full suite on builds, fix rounds and release cuts: `check-repo.py` and `check-changelog-pr.py` always, the test named for each changed script, render and parity tests when templates or fixtures change, and release and changelog tests for a cut. Diffs touching shared plumbing (`scripts/crew.d/_shared.py`, `scripts/crew`, the config and render cores) still run the full suite locally. The PR Testing section lists the set and its coverage reason; PR CI runs the full suite, and red CI still returns as a ci-red round. AGENTS.md, the tmux builder brief, Grok Bot B1 and their render and parity fixtures follow the new rule.
