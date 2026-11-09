---
type: added
issue: 1056
pr: TBD
date: 2026-11-09
box-skill: none
---

`crew-render` now prints, after a successful render, one stderr line per role brief with its path-normalized bytes against its `[size_budget]` (the measure bootstrap's self-test checks) and its delivered bytes, which add core memory and render notes. It warns when a brief is within 5% of its budget or over it, so a pack sees template growth before a release breaks its render. Written paths on stdout and exit codes are unchanged.
