---
type: added
issue: 1220
pr: TBD
date: 2026-11-06
box-skill: none
---

`scripts/metrics-baseline.py` reports, for closed crew PRs over a chosen window (optionally one milestone), the medians of issue-to-PR, PR-to-first-verdict, verdict-to-land, handoff ack latency, rounds per PR, defects caught by review or validation, and recorded engine runs per PR, with a per-PR table. The first baseline, covering M25, is committed as `docs/metrics/baseline-m25.md` so the reorganization can be compared against it. Measurement only; no crew behaviour changes.
