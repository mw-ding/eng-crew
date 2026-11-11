---
type: fixed
issue: 1417
pr: 1703
date: 2026-11-11
box-skill: none
---

`scripts/check-changelog-pr.py` now fails a PR that changes a released `CHANGELOG.md` section: every `## ` section below `## [Unreleased]` must stay byte for byte as at the merge base, so a PR, a cut included, may only add a new version section on top and edit `[Unreleased]`. The check runs before the exempt-path and fragment success paths, so a new fragment no longer lets a released-section edit through, and the failure names each changed section. CONTRIBUTING states the rule next to the fragment rules: restore the released section and record the correction in a new fragment. Replaying the guard over `CHANGELOG.md` history passes the 7.6.0, 7.7.0 and 7.8.0 cuts and flags only the two past late-fragment folds into an already cut section (#920, #1434), which the cut freeze (#1433) now prevents.
