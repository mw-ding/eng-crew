---
type: added
issue: 492
pr: TBD
date: 2026-11-01
box-skill: deferred to #140
---

tmux profiles can configure ordered standing runtime note files per role in `runtime.options.notes`. Each launch appends the current file contents under a heading naming the file; missing or unreadable notes block launch. Worker spawns and coordinator startup load their own notes, and omitted notes leave briefs unchanged. The profile and runtime docs explain configuration, and the coordinator brief uses this option instead of repeated manual policy sends.
