---
type: added
issue: 1462
pr: TBD
date: 2026-11-08
box-skill: none
---

The A31 campaign-history report reads actual campaign records (#804). `scripts/campaign-report.py capture` stores one milestone's crew PRs, closed in a window, as `metrics-refresh.py` rows, together with the decision log's `[Ash/decision]` records from that window. `report` renders the per-lane counts and denominators for the standard, express and solo lanes, the timing medians and the owner decisions. Empty lanes print `n/a`, and blank fields, a missing decision log and token counts are listed as missing. `docs/metrics/a31-campaign-report.md` is the M25 report rendered from the recorded capture, and `dev/tests/scripts/test-campaign-report.py` pins it and checks the per-PR rounds against `baseline-m25.md`.
