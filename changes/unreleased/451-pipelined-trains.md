---
type: added
issue: 451
pr: 455
date: 2026-11-01
box-skill: tmux brief rendered; live deployment deferred to coordinator
---

Prepare successor merge trains while a predecessor runs CI or lands, with
`train build --after N --no-wait` and `train wait N`; rebuild a successor
on current main after its predecessor stops. Landing stays serial and
head-bound. `train check` reports read-only gate snapshots, with manual
verification named explicitly. Pairwise merge checks defer likely conflicts
before a train merge, while clean shared-file pairs stay together.
