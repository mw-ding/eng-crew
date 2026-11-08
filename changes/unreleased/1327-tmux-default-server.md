---
type: changed
issue: 1327
pr: 1335
date: 2026-11-07
box-skill: none
---

The tmux runtime now runs the crew on the owner's default tmux server by default, so plain `tmux ls` lists the session and `tmux attach -t <session>` attaches; the dedicated `tmux -L <session>` server from #818 is opt-in with `runtime.options.tmux_server = "dedicated"`. The trade-off: on the default server a stray `tmux kill-server` from a pane also takes down the owner's own sessions; the #817 guard stays the primary protection. A crew session still running on the other server is used there until its next `mdstack up`, and an unknown value fails `validate`.
