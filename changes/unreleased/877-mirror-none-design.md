---
type: added
issue: 877
pr: 954
date: 2026-11-04
box-skill: none (design doc only; no docs/protocol.md or rendered template change)
---

Design for `runtime.options.mirror = "live-copy" | "none"` in
`docs/runtimes/tmux.md`: a tmux install with no live copy outside its
render opts in to `none`, and the no-mirror-hold gate resolves to a
recorded `n/a` (`train check` reason `n/a: profile mirror = none`, merge
record `Mirror: n/a (profile)`). It specifies validation (refused for Grok
Bot or with a mirror deferral), the gate order, an inert existing
`crew:needs-mirror` label, brief changes and build issues B1–B3
(#940–#942). Design only: nothing changes until those land, and the
default keeps today's behaviour byte-identical. `runtime-options.md`
points to it as proposed.
