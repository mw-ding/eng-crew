---
type: fixed
issue: 721
pr: TBD
date: 2026-11-03
box-skill: none
---

`crew train check` counts only artifact-shaped `evidence/` references as required artifacts: a path with a file extension, a markdown link or image target, or a backticked path. Prose such as "scope, evidence/citation, direction rule" no longer blocks a land with a missing-artifact result, and a missing artifact-shaped path still blocks.
