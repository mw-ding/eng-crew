---
type: fixed
issue: 1654
pr: 1664
date: 2026-11-11
box-skill: none
---

Two watcher tests no longer flake in CI. The upgrade test that stops a lock-holding watcher whose PID file was lost now waits for the stopped holder to exit instead of polling it once, since the kernel frees the lock before the exiting process can be reaped. The `mdstack up` persistent-watcher test now waits until its watcher frees `wake/watcher.lock` before the temporary directory is removed, so a scan still writing `wake/` no longer fails the teardown. The upgrade and watcher code was already correct and is unchanged.
