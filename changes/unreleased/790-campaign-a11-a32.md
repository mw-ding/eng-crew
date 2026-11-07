---
type: added
issue: 790
pr: 1075
date: 2026-11-06
box-skill: none (internal campaign fixtures and doc; no template or box-skill changes)
---

The M25 campaign gains the A11 (standard PR pipeline, precheck, rigor and rounds) and A32 (engines, quota steers and overrides) scenario specs in `scripts/fixtures/campaign/` (25.08). They run on real sandbox tmux at level a. A11 covers standard and missing item records, a tightening path, a build with seeded red CI that is reviewed but not validated, the CI fix with a fresh review, precheck refusals repaired to a pass, changes returned once, a round-2 fresh review and validation with no copied verdict, approval to the synthesizer, close-out on merge and an escalated change that starts no review. A32 covers tier order and effort matching the launch, a role override, reviewer diversity against actual builder engines, refusal when no diverse engine is left, a quota steer and Muse never launched on a private or unverified repo.
