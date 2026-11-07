---
type: fixed
issue: 1256
pr: TBD
date: 2026-11-07
box-skill: none
---

Twenty unreleased changelog fragments that merged with `pr: TBD` now carry their PR numbers, each taken from the merge commit that added the fragment. `scripts/changelog-cut.py` refused them, so the `release.yml` simulated cut failed on every PR touching a release file and the next release cut was blocked.
