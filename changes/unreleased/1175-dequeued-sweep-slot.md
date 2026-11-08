---
type: fixed
issue: 1175
pr: TBD
date: 2026-11-08
box-skill: none
---

The watcher's triage timer no longer lets a `queued` slot in `triage/sweep.json` hold back a milestone-close sweep after the queued sweep left `spawn-queue.jsonl`. Before, once a capped sweep was dequeued and started, the slot kept reading `queued`, so a milestone closed after that sweep waited up to `interval_hours` for the next sweep. Now the `queued` exemption holds only while a sweep request is still queued (an unreadable queue counts as holding one), and a later closed milestone sweeps at once, as `docs/triage.md` describes for a milestone close.
