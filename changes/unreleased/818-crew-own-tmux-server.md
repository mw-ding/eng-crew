---
type: fixed
issue: 818
pr: TBD
date: 2026-11-06
box-skill: none
---

The tmux crew now runs on its own server, `tmux -L <session>`, so an agent's bare `tmux` inside a crew pane (which follows the pane's `$TMUX`) can no longer take down the owner's default server or another crew; a session started before this change keeps working on its old server until its next `crew up`, and `crew up` prints the `tmux -L` attach line. After a lost server, `crew up` also stops a recorded pool lead whose pane process survived (Codex ignores `SIGHUP`), matched by its recorded pid, start time and parent pid 1, and leaves every other process alone. The campaign sandbox tmux shim now lets a crew's `-L NAME` through, since its pinned `-S` socket overrides `-L`.
