---
type: changed
issue: 900
pr: 1047
date: 2026-11-05
box-skill: none (docs-only)
---

The onboarding runbook's `Step 7: listener wiring per bot` opening, through
both routine ownership and creation-order tables, moves verbatim into
`docs/runbooks/grok-onboarding.md` (M26 modular organization, batch 3,
folded-in #902), with the rendered and hand-fill routine origins, the linked
Grok Bot cross-runtime limits, the merge-up distinctions and `pass=ack`
exclusion, the five rules for all routines, both full tables, the parent-turn
creation and verification and the lighter-lane qualification; the runbook
keeps the exact Step 7 heading as a direct module link and names the
per-routine details, steering wiring and cutover as still below;
`scripts/test-render-parity.py` reads the cross-runtime-limits link from the
module instead of the runbook; no rule, gate, marker or default changes.
