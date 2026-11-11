---
type: fixed
issue: 1020
pr: TBD
date: 2026-11-10
box-skill: none
---

A reviewer `work` handoff whose ref is not a readable JSON object (a markdown note, a missing file, a JSON list) no longer stalls the reviewer queue or hides its admission. `mdstack reviewer-pool` records it as `blocked: <id> invalid-work-ref <path> <reason>` in the reviewer lead's status, which route keeps for the coordinator, marks the handoff done and goes on to the next message. `mdstack schedule snapshot` lists it as an unranked `invalid-work` item with its `error` instead of making the whole reviewer demand `unknown`. Valid work behind it is still dispatched, and deferred valid work still replays.
