---
type: fixed
issue: 1343
pr: 1393
date: 2026-11-08
box-skill: none
---

A reviewer's done line with a trailing note after the verdict, such as `done: #<n> <sha> review pass validation required; CI red`, now routes like the bare line: `mdstack route` records the reviewer event, the reviewer lead starts validation, the scheduler ranks the event as the pass it starts, and a `changes` verdict still goes to the builder lead. Before, the anchored match dropped the line, so validation never started and the pass was never reclaimed. A note that contains the word `stale` no longer reads as a stale line. A builder's done line already allowed a trailing note (#695).
