---
type: added
issue: 181
pr: TBD
date: 2026-11-01
box-skill: pending coordinator mirror
---

Optional `builder.precheck` profile settings supply lint, test and docs commands
and a positive fix-attempt limit. Enabled profiles render ordered builder steps;
disabled profiles retain existing briefs, and missing commands render as `n/a`.
Validator and renderer tests cover the switch and layered overrides. No merge
gate change.
