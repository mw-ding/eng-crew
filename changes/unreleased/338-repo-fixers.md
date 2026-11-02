---
type: added
issue: 338
pr: 402
date: 2026-11-01
box-skill: none
---

`crew doctor` checks and repairs GitHub repository prerequisites: the runbook's
crew labels, a confirmed current milestone, a linked Project with four Status
options, and the reviewer invitation. `--dry-run` prints plans without local
or remote writes. Namespace collisions stop label repairs, populated boards
keep their Status options, and CI and branch protection remain human steps.
Bootstrap passes the new doctor options explicitly for its prerequisite checks.
Post-apply bootstrap checks also pass these options, and doctor retains the
profile's tool drift checks alongside repository repairs.
