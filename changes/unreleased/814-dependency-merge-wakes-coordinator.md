---
type: fixed
issue: 814
pr: 1063
date: 2026-11-05
box-skill: none
---

A dependency merge now wakes the coordinator within one watcher poll instead of waiting for the 30-minute backstop: on `pr-merged`, `crew route` still runs the mechanical close-out, then lists open issues and, when any `Depends on` block names the merged PR or an issue it closes, leaves the wake queued with `consumer=coordinator` and `dependents` (the waiting issue refs) so the coordinator dispatches the unblocked work at once. `crew watch` now ignores route's added notes (`consumer`, `dependents`) when it matches a kept record against the wake it routed, so the annotated record still ends the scan and wakes window 0; before, any record route annotated looked new and the watcher slept on. A merge nothing depends on is still consumed without a coordinator turn; a failed issue read leaves the wake queued, so the coordinator is woken rather than missed.
