---
type: fixed
issue: 1174
pr: 1408
date: 2026-11-08
box-skill: none
---

The committed A04 campaign scenario passes at `main` again: its `issue-list.json` fixture now carries the `body` field that real `gh issue list --json number,body` always returns, which `route.py`'s `dependents()` has requested since #1063. Committed scenarios do not run in CI, so `dev/tests/scripts/test-campaign-run.py` now checks that every committed scenario's `issue-list.json` literal carries the fields `dependents()` requests; it reads those fields from `route.py`, so the next requested field fails CI instead of a campaign rerun. The M25 `variants.py` no longer patches the body in itself.
