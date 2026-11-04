---
type: added
issue: 881
pr: TBD
date: 2026-11-04
box-skill: pending coordinator mirror (docs/protocol.md changed)
---

`[builder.precheck]` takes optional `owners` (a shell command that maps one
changed path to its owning test targets) and `no_owner_ok` (globs for paths
such as build files and docs that may have no owner). The new
`crew-config.py precheck-scope` reads changed paths on stdin, one per line so
spaces survive, and prints each path's class (`owned`, `no-owner-ok`,
`unowned`) and the owning targets as JSON. It exits 3 on unowned code and 4
when the owners query fails; both stop the check. `tests=n/a` now holds only
when every path is no-owner-ok. With `owners` set, the rendered pre-review
step tells the builder to run the helper. Without `owners`, behaviour and
render are unchanged.
