---
type: changed
issue: 368
pr: 379
date: 2026-11-01
box-skill: none
---

M14.3 tmux polish close-out (part of #110): the README Status marks M14.3
done (#301, #303, #312, #270, #262), and `docs/specs/portable.md` §5 gains
an M14.3 table with each slice `done` and its merged PR (status only, no
requirement changes). The runtime contract's C5 `ambiguous` row in
`docs/runtimes/README.md` no longer says a flat "never restart": it names
the tmux binding's two kill-and-respawn exceptions, the dialog rule and one
respawn of a stuck synthesizer after a failed nudge (#312), and links Q7 of
`docs/runtimes/tmux.md`.
