---
type: fixed
issue: 814
pr: TBD
date: 2026-11-05
box-skill: none
---

A dependency merge now wakes the coordinator within one watcher poll instead of waiting for the 30-minute backstop: on `pr-merged`, `crew route` still runs the mechanical close-out, then lists open issues and, when any `Depends on` block names the merged PR or an issue it closes, leaves the wake queued with `consumer=coordinator` and `dependents` (the waiting issue refs) so the coordinator dispatches the unblocked work at once. A merge nothing depends on is still consumed without a coordinator turn; a failed issue read leaves the wake queued, so the coordinator is woken rather than missed.
