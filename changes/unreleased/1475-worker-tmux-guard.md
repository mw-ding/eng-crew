---
type: fixed
issue: 1475
pr: 1482
date: 2026-11-08
box-skill: none
---

A bare `tmux kill-server`, `kill-session` or `kill-window` run from a worker or lead window no longer reaches the crew's server: the tmux adapter opens every role window with `TMUX=/dev/null/mdstack-worker,0,0`, a socket no server can listen on, while crew commands keep naming their server with `-S` or `-L` with the crew still on the owner's default server and no private socket (#1474, #1155, #817). The builder, reviewer and researcher tmux briefs carry the rule for destructive tmux calls and targeted test runs, and a decoy test runs the bare calls against a throwaway crew server.
