---
name: dispatch
description: Coordinator dispatch policy (milestone admission, plan gate, spec bookends and work-unit issues for new builds).
---

# Dispatch

Trigger: choosing the next build to dispatch.

- [milestone-admission.md](../../milestone-admission.md): at most the
  profile's active milestones, in order.
- [plan-gate.md](../../plan-gate.md): only items in an owner-approved
  plan, with its exceptions and the platform preflight.
- [spec-bookends.md](../../spec-bookends.md): a milestone opens with its
  spec slice and closes with its status-sync slice.
- Work-unit issues (`docs/roles.md`): file one issue per feature, fix or
  design, never a slice cut to a line budget; one PR per issue, split into
  logical commits. Separate work, owner-decision or design-first items and
  gate-contract changes keep separate issues; doc moves keep M26 principle 9.

Routing, caps and the watcher stay in each runtime template.
