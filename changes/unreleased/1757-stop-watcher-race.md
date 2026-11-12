---
type: fixed
issue: 1757
pr: TBD
date: 2026-11-12
box-skill: none
---

`mdstack down`, `mdstack upgrade` and `mdstack handoff stopped` no longer exit 1 with a `ProcessLookupError` traceback when the watcher exits between the PID read and the SIGTERM: a process that is already gone counts as stopped. `mdstack land-lock release` does the same for a recorded holder that exits after its identity check. Any other signal error (for example `PermissionError`) still raises.
