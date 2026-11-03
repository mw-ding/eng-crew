---
type: added
issue: 638
pr: 656
date: 2026-11-03
box-skill: none (session template; no Grok Bot routine changes)
---

Add a paste-ready coordinator-session brief (`templates/runtimes/session/coordinator.md`) that carries the ownership guard and the runtime handoff outgoing and incoming steps until the session binding exists, and `crew ownership --runtime session`, which checks the record as `session@<runtime.instance>`. This is build issue B of the runtime handoff design.
