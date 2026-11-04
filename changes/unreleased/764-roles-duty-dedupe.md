---
type: changed
issue: 764
pr: 833
date: 2026-11-04
box-skill: pending coordinator mirror (Grok Bot `eng-crew-roles` renders `docs/roles.md`)
---

`docs/roles.md` no longer restates the metrics-gate, knowledge-routing,
self-improve intake and land-rule duties in full. Each paragraph keeps the
owning role and its authority, then links the canonical home:
`docs/metrics/decisions.md` (trigger path and gate), `docs/self-improve.md`
(knowledge routing, always-loaded files, roles) and protocol §7 land rules
and merge trains. Every removed qualifier already lives there. Structural
only; no rule, gate or marker change.
