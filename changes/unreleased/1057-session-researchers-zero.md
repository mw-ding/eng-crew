---
type: fixed
issue: 1057
pr: 1510
date: 2026-11-09
box-skill: none
---

A `runtime.name = "session"` profile now accepts `runtime.options.researchers = 0`, the documented no-researcher statement, instead of refusing it as an unknown key, so a profile migrated from tmux keeps it. It is a no-op: the session binding has no researcher and renders the same briefs. Any other value is refused with a message saying the session runtime has no researcher. tmux handling is unchanged.
