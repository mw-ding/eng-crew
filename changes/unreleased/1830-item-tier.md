---
type: added
issue: 1830
pr: 1868
date: 2026-11-13
box-skill: none
---

`mdstack spawn` now carries an item's execution tier to every launch: the coordinator's signed `pass=flavor` record takes an optional `tier=trivial|default|deep`, and a builder or reviewer spawn without `--tier` takes the newest such allocation (a later flavor-only record keeps it) before the role default. A review, validation or recheck reads the PR's linked issues and refuses conflicting tiers; a malformed tier or unreadable item refuses before any claim, queue entry or window. Route and train fix and review dispatch no longer force the default tier, and the queue and run records keep the resolved tier through dequeue, restart and quota relaunch.
