---
type: changed
issue: 616
pr: 618
date: 2026-11-02
box-skill: none
---

A release cut PR may carry a release-pipeline fix (`release.yml`, `ci.yml`, `scripts/release-*.py` or `scripts/changelog-cut.py`) without a fragment: `check-changelog-pr.py` recognises a cut diff and instead requires a new entry naming the issue in the new version section. Any other change in a cut, or a non-cut change without a fragment, is still refused.
