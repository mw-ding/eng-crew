---
type: added
issue: 747
pr: TBD
date: 2026-11-03
box-skill: none
---

`crew poll` runs the always-on triage scan when `triage.enabled` is set (T1 of the triage design): with no model call it writes `triage/queue.json` with the unplaced issues and owner replies to triage records in each `triage.repos` tracker, skipping `triage:log` issues, placed or flavor-recorded issues and pull requests; each entry carries exact-key duplicate hints across open and closed issues, intake-card fields parsed from the card template and P0 signals from the rules file or built-in defaults. Unreadable repos and items are recorded, and a newly seen P0 candidate queues one `triage-p0` wake for the coordinator.
