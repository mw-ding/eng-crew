---
type: changed
issue: 615
pr: TBD
date: 2026-11-03
box-skill: none
---

**Breaking:** The release gate now also requires a green `ci.yml` push run at the cut's exact SHA. `release.yml` adds a `ci-gate` job that waits up to 40 minutes for that run and refuses publishing on a red, cancelled, missing or still-pending run; `workflow_dispatch` runs the same check at the dispatched commit. The `validate` job drops its own `check-repo.py` and every-test loop (now 10 minutes) and keeps only release-specific checks; `ci.yml` runs the suite once. `ci.yml` cancels superseded runs only for pull requests and groups `main` runs per commit, so a quick second merge no longer cancels the cut's CI. A publishing run whose actor is not `RELEASE_OWNER` now fails in `prepare`, before validation, naming the fix (dispatch as the owner account, or have the synthesizer merge). Migration: after a CI refusal, re-run CI to green, then re-run the failed release jobs. The release design and gate registry row describe the sequenced gate.
