---
type: changed
issue: 619
pr: 643
date: 2026-11-02
box-skill: none (tmux only)
---

Lead admission is caps only by default: the hard-coded one-minute load gate (`load >= cpus`) is gone and `max_suites` no longer defaults to `cpus // 4`. Two optional gates, both unset by default, defer expansion when reached: `max_suites` on observed local suites and the new `max_load`, a positive number compared with the one-minute load average. A missing load or suite observation defers admission only when a configured gate needs it, and an empty reviewer pool still keeps one slot at a reached gate. This is build issue S1 of the crew scheduler design.
