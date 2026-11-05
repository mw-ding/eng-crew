---
type: added
issue: 875
pr: 949
date: 2026-11-04
box-skill: none (design doc only; no rendered template change)
---

Tracker-native control item design in `docs/handoff.md`: a backend map's
optional `[ids]` table declares item and change id patterns once; a
`repo.control_item` may be an integer or a string matching the tracker
backend's item pattern; control-item commands use `<control-item>`, and a
legacy `<n>` map still works for integer ids. It specifies the
backend-neutral `read-item` output (author, body, created, optional id),
the `write-item` re-read-before-retry rule, the `crew handoff` live reads
through declared operations, and build issues F1–F4 (#936–#939). Design
only: nothing changes until those land, and every addition is optional
with today's GitHub behaviour as the default. `interfaces.md`, `profile.md`
and `packs.md` point to it as proposed.
