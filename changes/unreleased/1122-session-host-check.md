---
type: changed
issue: 1122
pr: 1513
date: 2026-11-09
box-skill: none
---

`mdstack host check` and `mdstack host prepare` now run for a `runtime.name = "session"` profile instead of exiting 1 with `runtime.name is session, not tmux` before any readiness row. `validate` accepts a `[hosts]` inventory on a session profile (still not `[placement]`, which only tmux spawn uses); the primary gets `mdstack doctor`'s session rows, engine login and project mirror rows with load 0, and other hosts get the same remote rows as under tmux. The shared profile guard takes the runtimes a command supports, so every other command and tmux behaviour are unchanged; `hosts`, `layout` and `upgrade` stay tmux-only.
