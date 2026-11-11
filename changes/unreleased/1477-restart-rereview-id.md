---
type: fixed
issue: 1477
pr: TBD
date: 2026-11-10
box-skill: none
---

A reviewer pass now keeps its rereview identity across a clean restart and the spawn queue: `mdstack spawn` takes `--rereview-id` (reviewer only, with `--pr` and `--head`) and writes it into the run record before the harness starts, a queued request carries it to `mdstack dequeue`, and a clean `mdstack restart` passes it with the run's head, so a moved head refuses as stale instead of inheriting the old steer. The reviewer route hands the steer to spawn instead of patching the record afterwards, so a restart after a session loss no longer opens a duplicate same-head review and round-cap escalation.
