---
type: fixed
issue: 1302
pr: TBD
date: 2026-11-08
box-skill: none
---

A builder whose spawn `build` nudge landed in a trust dialog, so it never acked it, now counts as idle once its `done:` line names that issue. Before, the unacked message kept the finished, pushed builder busy forever, which blocked `dequeue` idle reclaim and held scheduler capacity. Unacked fix, CI and other-issue messages still keep it busy.
