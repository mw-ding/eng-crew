---
type: changed
issue: 777
pr: TBD
date: 2026-11-03
box-skill: deferred to #140
---

Grok Bot routes express items through the crew lane. Express stays an option there but is not enabled, and no self-gate runs. B1, V1, V2 and S treat a `crew:express` label or express item record as the crew lane (normal resolution, independent review and validation, approval to land) and route the item back to the coordinator. The wiring doc's new section 2d has the coordinator post a signed `pass=flavor` record with the item's normal flavor and remove `crew:express` before dispatch. On grok-bot, `crew doctor` adds a `triage` row: `ok` when off, `warn` when `triage.enabled = true`, because Grok Bot installs no triage timer and triage stays coordinator dispositions. Bootstrap's plan says the same and never claims a timer install. The bootstrap preflight table gains row 23.
