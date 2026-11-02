---
type: fixed
issue: 510
pr: 515
date: 2026-11-01
box-skill: none
---

Keep the synthesizer alive during an unfinished land, held land lock or open
train, including merged-PR cleanup. Save pending lands in run state and restore
them after kill or crash; name open trains and recovered inbox IDs on spawn.
Unacknowledged retries ignore historical completions for the same PR.
Bind detached land-lock holders to the owning pane's process identity, and
clean up dead or orphaned holders without signalling a live owner or reused PID.
Allow the expanded repo-guard suite ten minutes in CI.
