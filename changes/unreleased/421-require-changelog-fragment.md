---
type: added
issue: 421
pr: TBD
date: 2026-11-01
box-skill: none
---

CI requires a newly added changelog fragment for PR content changes, using
the PR merge base and a documented exempt path list. Cut output, fragment-only
changes, verification artifacts and empty diffs pass without a new fragment;
pushes to main skip the requirement.
