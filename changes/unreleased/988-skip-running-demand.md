---
type: fixed
issue: 988
pr: TBD
date: 2026-11-04
box-skill: none (script and docs/scheduling.md only; no docs/protocol.md or rendered template change)
---

`crew schedule decide` skips demand that a busy worker of the same pool is
already running, matched on the worker's `pr` or any `#n` in its item. Such
an item is no longer admitted, held or counted against the pool cap, the
target or the ramp limit, so one in-progress item (for example a merge-up
whose run record has `pr: null`) no longer uses up `schedule_ramp` and
defers the rest of its pool with reason `ramp`. The item stays in demand
until its lead marks it done.
