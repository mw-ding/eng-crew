---
type: added
issue: 1219
pr: TBD
date: 2026-11-06
box-skill: deferred to #140
---

The essential project doc set now has six docs: `docs/specs/` joins it as every project's source of truth, each spec carrying the design-doc status banner. A new spec template (`templates/spec.md`) seeds one with stable `REQ-` requirements (applies when, obligation, acceptance criteria, verification), open questions and a change table. eng-crew adopts its own doc set: `docs/decisions.md` is seeded from the #985 decision log, and `docs/runbook.md` is the runbook entry point linking the install, run, release and recover owner docs. The `[docs] homes` key and docs-pass check for specs come with the bootstrap scaffold (#1225).
