---
type: added
issue: 624
pr: TBD
date: 2026-11-03
box-skill: none
---

`crew schedule decide --pool builder|reviewer` makes the crew scheduler's admission decision under `schedule/lock`. It ranks both pools' demand, grants the caller's items within the pool cap, the target T, the ramp limit and the optional `max_suites`/`max_load` ceilings, and reserves only the caller's grants in `schedule/reservations.json` (they expire after 600 seconds or when a run record appears). The other pool's would-be grants become holds for that walk only: they are dropped as `lead-down` when that pool's lead is down, and otherwise the owning lead gets a backstop nudge. Each pool's floor admits its top item past T, the ramp and the ceilings. Every decision appends a snapshot line and its admits, holds and new defers to `schedule/decisions-<yyyymmdd>.jsonl` (7 days kept). `crew schedule release` frees a reservation after a failed spawn. The builder lead brief now calls `schedule decide` instead of `crew lead capacity`; the reviewer lead is unchanged until S7.
