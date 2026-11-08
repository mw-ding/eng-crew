---
type: fixed
issue: 1092
pr: 1374
date: 2026-11-08
box-skill: none
---

A researcher's queued `done:` or `failed:` wake no longer kills a fresh run that reuses its window name (`riley-sweep`, `riley-<n>`). Each status wake from `mdstack watch` now names the run that wrote it (its start time, pane and worktree), and `mdstack route` reaps a researcher only when the wake's run matches the live record. Before, the wake stayed queued for the coordinator and every later route pass applied it again, so a sweep or follow-up deep dive started before the coordinator drained was killed at the next watch tick. Wakes queued before this change, which carry no run, still reap as before.
