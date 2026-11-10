---
type: added
issue: 1522
pr: 1546
date: 2026-11-09
box-skill: none
---

Reflection now files recurring-pattern cards without approving them (#1403 R6). New `scripts/reflection-candidates.py` reads `reflection-scan.py`'s evidence index, the forge snapshots and the findings buffer offline. It selects findings rows at count 3 or more and classes with 3 or more distinct incidents in the window. A fixed or applied row, or a pattern whose card closed, gives no new work without an occurrence after the fix. It matches open and closed work by proposal prefix, Failure class and batch issue, and answers `file`, `append`, `none` or `skip`. The researcher's `protocol-reflection` procedure gains a threshold-card step: it files an unchanged intake card with Decision `pending` inside the report cap and cooldown, or appends the new evidence. It rechecks before each post so a retried run reconciles a card it already filed, and it never edits the buffer, readiness labels or milestones. `docs/self-improve.md` points the threshold paragraph at both.
