---
type: added
issue: 750
pr: 774
date: 2026-11-04
box-skill: deferred to #140
---

Add triage shadow mode's precision bar (M24 T4, `docs/triage.md`): `scripts/triage-metrics.py` draws the calibration sweep's 10-record spot check (deterministic per sweep id), scores the 8-of-10 bar from `owner-accepted` / `owner-rejected` records, reports accuracy, owner override rate, reopen rate, time to triage, proposals per day and tokens per sweep, and freezes and re-scores the eval set of owner-confirmed records. The researcher's triage-sweep brief gains Calibration (the first sweep records the whole backlog without the noise cap and lists the spot check in the day's log) and Measures bullets, and never sets `triage.mode`: only the owner sets `apply`. The `pass=triage-log` line gains `tokens=`; the GitHub `list-items` mapping adds `stateReason,createdAt`.
