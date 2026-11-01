---
type: added
issue: 178
pr: TBD
date: 2026-11-01
box-skill: none
---

Session backend interface: `docs/runtimes/session-backends.md` defines what a
runtime needs from the program hosting its role sessions (create in the
background, attach read-only by default, doorbell, identity probe, state read,
kill), each tied to the runtime contract capability it serves. The identity
probe restates C5 as backend operations: a unique handle plus a start time,
recorded at spawn, and a different handle or start time probes `missing`,
never `alive`. tmux is filled in from `scripts/crew-tmux.py` and the tmux
binding. The runtime contract links it from a new `## Session backend
interface` section; the docs index, deliverables inventory and manifest, and
required-docs list gain its row. Docs only; no rule, gate or code change.
Roadmap 15.5.
