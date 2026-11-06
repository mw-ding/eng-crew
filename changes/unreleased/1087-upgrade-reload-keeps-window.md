---
type: fixed
issue: 1087
pr: TBD
date: 2026-11-06
box-skill: none
---

`crew upgrade --yes` now reloads roles on real tmux instead of destroying the first role's window. The reload stopped the pane's process group, which was the window's only process, so tmux removed the window and the following `respawn-window -k` failed with `can't find window`, leaving the new install recorded with no role reloaded. Each reload now sets the window's `remain-on-exit` before the stop and unsets it after the respawn, so the window survives and every role restarts in place, coordinator last. A new test runs the reload against a real tmux server on a private socket. Found by the M25 A20 run on #796.
