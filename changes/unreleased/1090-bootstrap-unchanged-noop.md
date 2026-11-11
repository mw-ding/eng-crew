---
type: fixed
issue: 1090
pr: TBD
date: 2026-11-11
box-skill: none
---

`mdstack bootstrap` re-run with nothing changed now prints `crew bootstrap: no changes`, exits 0 and writes nothing: no target, link, exclude or `install.json` rewrite and no self-test. It compares the full planned install (record fields, target bytes, link, exclude lines, pending removals and scaffolding, and any deployed render) with the live one; a changed input or a failed previous install still re-applies, and edited-target refusals are unchanged.
