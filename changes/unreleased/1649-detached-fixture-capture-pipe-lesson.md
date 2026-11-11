---
type: added
issue: 1649
pr: TBD
date: 2026-11-11
box-skill: none
---

Lessons log: new lesson on a detached test-fixture child that inherited the `capture_output` pipe, so each launch waited about 60 seconds for EOF and repo-guard CI hit its job limit. It records the DEVNULL stdio repair from #1637, the unchanged assertions and the published measurements.
