---
type: added
issue: 1524
pr: 1528
date: 2026-11-09
box-skill: none
---

Added reflection effect measures (#1524). `mdstack poll` now records a sanitized ready sample per crew PR when its head, CI, verdict, mergeable state or hold changes, with the previous poll time as its sampling bound, and `mdstack watch` records one stall per new stale wake, closed by the run's next status line; both go to `metrics/observations.jsonl` in the state dir. The new offline `scripts/reflection-measures.py` joins these samples with the metrics CSV and explicitly confirmed false-throttle incidents to report verdict and CI-fix rounds per PR, observed ready-to-land minutes, unioned stall minutes and the false-throttle count, each with refs and coverage; missing history stays unknown and unconfirmed errors stay unclassified. Its ledger keeps each proposal's merge ref and confirmed activation, and saves a baseline only before activation. Operational ready is a sampled measure, never merge authorization.
