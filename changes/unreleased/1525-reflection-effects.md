---
type: added
issue: 1525
pr: TBD
date: 2026-11-09
box-skill: none
---

Reflection reports now evaluate every accepted proposal (#1403 R9). New `scripts/reflection-effects.py` joins the proposal, issue and merged PR chain from the coordinator's reflection-decision comments with the effect ledger and measures of `reflection-measures.py`. Each proposal gets one row: activation, its effect measure before and after, sample sizes, the repo and class cohort, missing data, status and the next evaluation date. A row stays pending until the change is merged, activated and a whole 14-day window has passed, and insufficient under 3 PRs on a side or with unknown counter coverage. An evaluated row recommends keep, revise or revert, never claiming a cause and reverting nothing. The researcher's `protocol-reflection` procedure attaches the table as an Effects section of each report, and `docs/metrics/decisions.md` points to it without changing any metrics-gate threshold.
