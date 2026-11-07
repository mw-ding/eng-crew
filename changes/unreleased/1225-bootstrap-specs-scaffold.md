---
type: added
issue: 1225
pr: TBD
date: 2026-11-07
box-skill: none
---

`crew bootstrap` now scaffolds the specs home of the essential doc set: when the checkout's `docs/specs/` (or the profile's `[docs] homes.specs`) holds no Markdown spec, the plan prints a `scaffold` repo operation and apply writes `project.md` from the spec template's skeleton, for the owner to commit; it never overwrites a file or seeds beside an existing spec, and the seed is not an owned install target. `[docs] homes` accepts a `specs` key (a directory, no anchor), and `docs-scan.py` reports a specs home with no Markdown spec under it as missing.
