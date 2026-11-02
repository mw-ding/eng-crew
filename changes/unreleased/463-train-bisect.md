---
type: added
issue: 463
pr: TBD
date: 2026-11-01
box-skill: none
---

`crew train bisect` tests ordered halves of a red train, identifies failing members and rebuilds survivors together on the default branch for normal head-bound landing. Failed predecessors cannot seed `--after`; green combined retries recover flaky trains.
