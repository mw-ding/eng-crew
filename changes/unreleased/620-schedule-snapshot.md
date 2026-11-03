---
type: added
issue: 620
pr: TBD
date: 2026-11-02
box-skill: none
---

`crew schedule snapshot` prints one JSON object with every crew scheduler input from the scheduling design: both pools' pending demand by kind, worker state, reservations, open trains, open milestones and issue dependencies, normalized load, memory pressure on macOS and Linux, local suites, recent gateway errors and each pool's cap. A failed read is `unknown` for that input only. It is read-only and changes no admission yet.
