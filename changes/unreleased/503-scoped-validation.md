---
type: changed
issue: 503
pr: 520
date: 2026-11-01
box-skill: deferred to #140
---

Reviewer validation runs acceptance checks, the repo guard, and tests covering changed files, citing green PR CI at head for the full suite. Verdicts list the local tests and CI link; red or missing CI remains the merge gate and cannot be replaced by a local full run. Both runtime templates and their render/parity fixtures follow this scope.
