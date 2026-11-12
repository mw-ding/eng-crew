---
type: added
issue: 1722
pr: TBD
date: 2026-11-12
box-skill: deferred to the coordinator mirror (protocol §7 stack text)
---

Session stack land for backends whose stack request names one representative change plus every member's revision id. `change.land-stack` may bind `<stack-top>` (the last member), `<stack-changes>` (member ids, base first) and `<stack-revisions>` (each member's immutable revision id, read by the new conditional `change.read-revision-id` at its checked head, one safe token, recorded in the intent before the first status read and reused, never re-resolved, by a rerun or resume). `land.stack_status = "per-change"` reads the stack back from each member's `change.land-status` through `[land.status]` and `change.read-landed` instead of `change.stack-status`; members in different states, queued beside landing included, are unknown and record nothing. A sync stack binding may now declare `land.change_placeholder`. Per-change readback refuses `land.stack_tests_against_tip`, so it never meets the tip gate. Legacy `<stack>` operation and every GitHub or unbound render are unchanged.
