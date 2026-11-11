---
type: fixed
issue: 1476
pr: 1622
date: 2026-11-10
box-skill: none
---

`mdstack route` now consumes obsolete recovery wakes instead of waking the coordinator. A `blocked:` line from a lead or a gone run is consumed when every item it names is closed or merged, or when its pinned PR head or review round is superseded. An open issue, the current head, an untyped line (such as `blocked: main red after #N`), a live worker's block or an unreadable item still reaches the coordinator. An idle builder reclaim records the reclaimed run's identity, and the watcher's stale wakes now carry their run identity. A dead or missing stale wake for that same run is consumed (#1552), but a replacement run under the same window name still wakes.
