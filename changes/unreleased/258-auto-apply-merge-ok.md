---
type: changed
issue: 258
pr: TBD
date: 2026-11-11
box-skill: none
---

Protocol §6 and the tmux runtime's C8 row now say the auto-apply deadline only wakes the coordinator to apply a permitted default: elapsed time never supplies a merge-ok, and a merge still needs the repository's own recorded standing grant or the owner's per-change merge-ok at head, plus every applicable gate. This clarifies the shipped coordinator brief; it adds no timer or permission rule.
