---
type: fixed
issue: 738
pr: TBD
date: 2026-11-10
box-skill: none
---

Spawn preflight for Claude Code as root: Claude Code exits at once in `bypass` permission mode when it runs as root, which left a worker window that vanished and surfaced only as missing probes. `mdstack spawn` (and restart and lead launches) now refuses a Claude Code role window in `bypass` when the launching process's effective uid is 0, before the window opens, with an error naming root plus bypass and the two fixes: run the crew as a non-root user, or set `runtime.options.permission_mode` to `auto` or `safe`. A remote run is checked on its execution host by that host's uid, never the primary's. The adapter contract gains an optional `launch_refusal(mode, uid)`. Non-root and non-bypass launches, and other engines, are unchanged.
