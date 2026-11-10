---
type: added
issue: 1052
pr: TBD
date: 2026-11-10
box-skill: none
---

The session runtime's `runtime.options.session_backend` accepts `hosted` for workers that are hosted sessions created through a control plane, addressed by the returned session id and probed by a control-plane state read. A hosted profile's coordinator and worker briefs render that dispatch and liveness text with no subagent, task-handle or PID language, through new `<session-backend:hosted>` and `<session-backend:local>` template blocks; `native` and `cli` profiles render byte-identically to before.
