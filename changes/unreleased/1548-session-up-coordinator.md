---
type: added
issue: 1548
pr: 1549
date: 2026-11-09
box-skill: none
---

`mdstack up` accepts a session profile (`runtime.name = "session"`) instead of refusing it as "not tmux": it starts only the interactive coordinator, in window 0 of the tmux session `runtime.options.session` (default `crew-<owner>-<repo>`), launched by its harness adapter with `CREW_ROLE=coordinator`, `CREW_PROJECT`, `CREW_STATE` and the rendered `runtime/coordinator.md` brief, and opens no role windows, so workers stay dispatched per pass. A running session prints its attach line instead. Session profiles now accept `runtime.options.session`, `permission_mode` and `launch` (`coordinator`, `resume`). A new `mdstack up --resume <id>` flag overrides `launch.resume` for one run, on tmux too. Other tmux behaviour is unchanged.
