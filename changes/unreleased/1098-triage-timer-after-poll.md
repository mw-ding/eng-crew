---
type: fixed
issue: 1098
pr: 1149
date: 2026-11-06
box-skill: none
---

`crew watch` now runs the triage sweep timer after each scan's `--source` commands instead of before them, so the timer's empty-queue check reads the `triage/queue.json` that scan's `crew poll` just wrote. Before, on the first scan after the machine resumed, the timer read the pre-pause queue, recorded the overdue slot as `skipped: empty queue`, and left the issues opened during the pause waiting a full `interval_hours` for their sweep.
