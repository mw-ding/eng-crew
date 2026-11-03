---
type: added
issue: 623
pr: 678
date: 2026-11-03
box-skill: none
---

The crew scheduler computes its crew-wide target T in `schedule/target.json`: T starts at the busy count, stays between 1 and the sum of the pool caps, and moves by one at most once per `schedule_interval`, down on any high signal (load, memory pressure, gateway errors) and up when every signal is low and demand waits; unknown signals hold it. A ramp limit counts starts per interval. New profile options `load_high`, `load_low`, `error_high`, `schedule_interval` and `schedule_ramp` are validated. No command calls the target yet; admission is unchanged.
