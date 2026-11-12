---
type: fixed
issue: 1715
pr: 1755
date: 2026-11-12
box-skill: none
---

The watcher's lead backstop no longer re-wakes a lead every 60 seconds with no state change. Unchanged pending demand now backs off 60, 120, 240, 480, then every 900 seconds, restarting when the pending set changes, and the timer survives a watcher restart. A lead marks an acknowledged id that waits on the owner, a hold or CI with `waiting: #<n> owner|hold|ci id=<id>`; no backstop, slot release or coordinator backstop re-types it while the ref's token-free fresh state (poll-state's observed PR, its hold and owner-answer count, an open owner ask) is unchanged, and a change wakes it on that scan. Other ids keep their own retries, untyped lines silence nothing, and an acknowledged admission deferral keeps #1502's 60-second admission recheck, which types only that id once its ref is admissible. The three lead templates gain the Waits paragraph.
