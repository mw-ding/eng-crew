---
type: changed
issue: 321
pr: 367
date: 2026-11-01
box-skill: deferred to #140
---

The merge train is now a standing synthesizer skill in the rules (#321, part
2a; part of #110). Protocol §7 gains the "tested with the default branch"
gate and its gate-registry row: the head contains the current default
branch, or the change is the next member of a green train on it. A new §7
section gives the owner's land rules (train two or more ready changes, merge
a lone or urgent one alone, wait briefly for one close to approval, never
past the window), and each merge record names its rule in a `Land rule:`
line. `docs/roles.md`, both synthesizer templates and the tmux runtime doc
follow it; the `train_min` and `train_window` profile options come in part
2b.
