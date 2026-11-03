---
type: changed
issue: 578
pr: TBD
date: 2026-11-02
box-skill: none (tmux only)
---

Cut coordinator wake noise from `crew watch`. An idle live lead or synthesizer, with no queued or in-flight work, no longer raises a stale wake. A synthesizer gate-status block that only waits on CI, review, validation or a train now carries `wait=<items>` and is recorded without a wake. `ci-failed` records for a superseded head are dropped by the poller and by route. A lead's `unblocked` message for a block that resolved itself is recorded in the coordinator inbox without a nudge.
