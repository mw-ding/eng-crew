---
type: fixed
issue: 1266
pr: TBD
date: 2026-11-08
box-skill: none
---

A regression test now covers a fresh builder spawn ending its own build reservation: a build grant for `#<issue>`, then `mdstack spawn builder --issue <issue>`, leaves no entry in `schedule/reservations.json`, and the decide-side matcher drops the grant against the spawned run record whatever its window state reads. A later grant with no new run record still stays live, and a refused spawn keeps its grant for the lead's release or the TTL. The three manual releases reported on 2026-11-07 came from a crew home older than the `mdstack spawn` release of #1050 (PR #1150); the test fails with that release removed and passes at the current head, so the scheduler is unchanged.
