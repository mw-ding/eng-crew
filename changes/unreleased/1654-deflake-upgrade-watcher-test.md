---
type: fixed
issue: 1654
pr: TBD
date: 2026-11-10
box-skill: none
---

The upgrade test that stops a lock-holding watcher whose PID file was lost no longer flakes in CI: it waits for the stopped holder to exit instead of polling it once, because the kernel frees the lock before the exiting process can be reaped. The upgrade code was already correct and is unchanged.
