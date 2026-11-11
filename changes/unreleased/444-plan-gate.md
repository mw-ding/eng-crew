---
type: added
issue: 444
pr: TBD
date: 2026-11-10
box-skill: none
---

Plan gate: the coordinator creates implementation items, adds a new `crew:ready` or dispatches a new build only for an item in an owner-approved plan (a milestone or project). "Start building" counts as a request to propose a plan, never approval. The owner's OK is a signed `[<CoordinatorBot>/steer] plan approved` comment with a `pass=steer cmd=plan-ok` marker on the plan's tracking issue, defined in protocol §6. The rule records open decisions before items are derived, reconciles a later owner change in one steer, and keeps the fix, CI, follow-up and owner-requested trivial-docs exceptions. It also adds the #396 environment preflight: a platform item becomes ready only when its spec cites dated, observed host, toolchain and device facts and lists every owner-only prerequisite up front. A new shared fragment `templates/policy/coordinator/plan-gate.md` puts the rule in the tmux, session and Grok Bot coordinator briefs. `templates/spec.md` gains Target environment and Owner prerequisites sections, and onboarding Step 8 records plan approval before the first `crew:ready`. Merge gates are unchanged.
