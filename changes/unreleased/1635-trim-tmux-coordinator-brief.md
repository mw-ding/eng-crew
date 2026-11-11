---
type: changed
issue: 1635
pr: TBD
date: 2026-11-10
box-skill: none
---

The tmux coordinator brief is 911 bytes smaller (15,300 to 14,389 path-normalized bytes against its 15,360-byte budget), freeing room for M44's pending brief additions. Long route bullets are reworded without dropping any rule, marker or command, and the merged-PR close-out detail, which `mdstack route` performs, moves to the tmux binding's `mdstack route` section behind a one-line pointer. The session coordinator brief and the size-budget constants are unchanged.
