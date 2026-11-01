---
type: fixed
issue: 361
pr: 393
date: 2026-11-01
box-skill: none
---

`crew watch` skips stale wakes for runs without `start` while their run-record
mtime is less than 60 seconds old, avoiding a false missing-run restart during
spawn. Older unfinished spawns and started runs with missing windows still
wake as missing and restartable. Regression tests cover all three cases.
