---
type: added
issue: 156
pr: 307
date: 2026-10-31
box-skill: none
---

Crew flavors (design): `docs/flavors.md` proposes per-project rigor
presets (`thorough`, `standard`, `fast`, `solo`) built from eleven knobs
(review depth, validation, engine diversity, caps, evidence, merge
permission, pre-review check, lighter lane, parallelism, engine routing,
builder); the floor F1–F7 (CI never waived, no secrets, synthesizer-only
land, audit on the record, owner hold, gate changes need the owner,
`crew:sensitive` needs a per-change merge-ok) with validator rules; a
`[flavor]` profile schema proposal; project / item / change resolution
per #160 row 15 (flavor chosen at intake, item flavor recorded at
triage, a stated reason to lower, no flavor = `thorough`, path-based
class rule, uncertain → stricter); a mapping of every existing one-off
knob; and the metrics feedback loop (inputs, thresholds T1–T3 and R1–R3,
suggestion issue, owner accept path, never auto-applied). Maps onto
build issues #195–#199, #102 and #109. `docs/flavors.md` is classified
as a deliverable and pinned in `scripts/required-docs.txt`. Adds no
rule, gate, cap, marker field or label. Roadmap 18.1.
