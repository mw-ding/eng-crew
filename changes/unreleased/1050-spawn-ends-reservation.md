---
type: fixed
issue: 1050
pr: 1150
date: 2026-11-06
box-skill: none
---

`crew spawn` now drops a builder or reviewer run's own `schedule decide` reservation (same pool, its `#issue` or `#PR` ref) as soon as the run starts. Before, `live_reservations` ended a grant only when a later decision saw a busy worker on the ref or one started since the grant, so a pass that started and was reaped between two decisions revived as a live reservation and held a pool slot until `reservation_ttl` (600 seconds), deferring other PRs with `cap` and no worker running (#1070, found by the M25 A07 run). Expired reservations were already ignored on `main`; spawn failures still leave the grant for the lead's `crew schedule release`.
