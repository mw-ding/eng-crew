---
type: added
issue: 1418
pr: TBD
date: 2026-11-11
box-skill: none
---

Moved or quoted prose keeps its meaning. A doc move records a source-to-destination qualifier comparison (trigger, runtime scope, conditions, exceptions) in the PR body, per a new Doc moves section in `CONTRIBUTING.md` (#1125). Before opening a PR, the builder cites the item's newest signed coordinator allocation and runs the new role helper `scripts/check-pr-linkage.py`: each allocated issue needs exactly one whole `Closes #N` line, a release cut uses #1416's release-only form, and every other closing keyword is flagged by line, descriptive mentions of closed issues included (#1131, #1211). A later reallocation is reported in a signed note, never fixed by a body edit. It is a builder duty in the build pass and PR conventions, not a merge gate.
