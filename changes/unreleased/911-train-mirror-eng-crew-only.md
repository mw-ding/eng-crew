---
type: fixed
issue: 911
pr: TBD
date: 2026-11-04
box-skill: none (script-only)
---

`crew train check` now treats `docs/protocol.md` and `templates/` as mirrored
paths only when the train runs on the eng-crew repo itself (`repo.name =
"eng-crew"`). A product repo with its own top-level `templates/` folder or a
`docs/protocol.md` gets `mirror: pass (no mirrored paths)` instead of blocking
on "no coordinator mirror/drift record". The `crew:needs-mirror` label still
blocks on every repo, and eng-crew's own mirror gate is unchanged.
