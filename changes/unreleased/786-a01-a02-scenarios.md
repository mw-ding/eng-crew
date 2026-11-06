---
type: added
issue: 786
pr: TBD
date: 2026-11-05
box-skill: none
---

M25 campaign scenarios A01 (config layers and provenance, two-repo team files, malformed capability, flavor floor lowering, fix-and-rerun recovery, external pack pin and bootstrap pin) and A02 (render overlay and runtime notes, missing mapping and note, drift detection and restore, long install path, size budget and render, parity and bootstrap tests) are committed as `scripts/fixtures/campaign/A01.json` and `A02.json` with their fixture profiles, and `campaign-run.py` expands a new `{source}` step placeholder to the pinned eng-crew checkout so a step can call its CLIs and stage fixtures. Harness specs only; the level-a run's results are posted inline on the PR and its one failed oracle is filed as an M25 finding.
