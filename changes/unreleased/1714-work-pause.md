---
type: added
issue: 1714
pr: 1767
date: 2026-11-12
box-skill: none
---

**Breaking:** new `mdstack pause` and `mdstack resume` give the owner a work pause that keeps the coordinator in window 0 and the watcher, instead of `mdstack down`, which ends window 0. Pause first writes a durable `pause.json` barrier in the state dir; while a land holds the lock it prints `pausing` and exits 75 with nothing stopped. Otherwise it stops every other window and each role-host run with every worktree, record, claim, inbox and status file kept. A surviving process or an unanswering host is an incomplete pause (exit 1, barrier kept). While the barrier exists or is unreadable, dispatch, messages, review pools, restarts, trains, land-lock acquire (rechecked under the lock), land requests, `gc --apply`, route, lead and lifecycle starts and `ownership --action start|land` refuse. `mdstack up` starts no role window, and the watcher only queues events: no scan, timer, routine, route or nudge. Resume checks ownership, removes only the barrier, restarts each run the pause stopped once without spending its one restart (held or `done:` runs stay stopped), restarts leads and lifecycle floors, and queues one `resume` wake for the coordinator. Protocol §7 gains a runtime-bound "No project pause" gate and §9 a Project pause section; the coordinator brief maps an owner pause to `mdstack pause`. Migration: none; an install with no `pause.json` behaves as before.
