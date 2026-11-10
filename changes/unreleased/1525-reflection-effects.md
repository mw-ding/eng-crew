---
type: added
issue: 1525
pr: 1556
date: 2026-11-09
box-skill: none
---

Reflection reports now evaluate every accepted proposal (#1403 R9). New `scripts/reflection-effects.py` joins the proposal, issue and merged PR chain from the coordinator's reflection-decision comments with the effect ledger and measures of `reflection-measures.py`. Each proposal gets one row: activation, its effect measure before and after, sample sizes, the repo and class cohort, missing data, status and the next evaluation date. Before and after are equal-length windows (the baseline's 14 days), both computed from inputs limited to the proposal's repos and Failure class, and each side shows its sample coverage. A row stays pending until the change is merged, activated and a whole window has passed, and insufficient when the inputs cannot place rows in the cohort, under 3 PRs on a side or with unknown counter coverage. An evaluated row recommends keep, revise or revert, never claiming a cause and reverting nothing. The researcher's `protocol-reflection` procedure attaches the table as an Effects section of each report, and `docs/metrics/decisions.md` points to it without changing any metrics-gate threshold.
