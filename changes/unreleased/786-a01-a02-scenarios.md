---
type: added
issue: 786
pr: 1067
date: 2026-11-05
box-skill: none
---

M25 campaign scenarios A01 (config layers and provenance, two-repo team files, malformed capability, flavor floor lowering, fix-and-rerun recovery, external pack pin and bootstrap pin) and A02 (render overlay and runtime notes, missing mapping and note, drift detection and restore, long install path, size budget and render, parity and bootstrap tests) are committed as `scripts/fixtures/campaign/A01.json` and `A02.json` with their fixture profiles; each step stages its fixtures from `{source}`. Harness specs only. The level-a run's results are posted inline on the PR; its one failed oracle (render-vs-live drift passing an altered command or appended live text) was filed as #1064 and fixed there, and A02 passes on rerun.
