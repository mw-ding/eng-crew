---
type: added
issue: 1441
pr: 1504
date: 2026-11-09
box-skill: none
---

Campaign scenario A29 runs the handoff round trip between two full teams (#213, #157). `dev/tests/scripts/fixtures/campaign/a28/teams.py --handoff` seeds the fake forge from `a29/handoff.py` with team a's claim, a dependency set, a change in review, a pending owner ask and a backlog item. Team b, which does not own the repo, starts read-only with only its coordinator. Once both teams are ready, the driver runs the real `mdstack handoff` commands a → b in drain mode and b → a in stop mode, and starts the new owner's whole team each way. The run fails unless the control item holds each state once per handoff id with exactly one ack, exactly one team (or none in transit) may write after every step, each `stopped` post finds the outgoing session gone, both manifests hold the same sets, stages and heads, the kept run is named, and nothing else was posted on or written to the forge. `docs/handoff.md` states the owner assumption and replaces the 21.5 row's Grok Bot example with the two-team environment.
