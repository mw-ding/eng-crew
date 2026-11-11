---
name: dispatch
description: Coordinator dispatch policy (milestone admission and plan gate for new builds).
---

# Dispatch

Trigger: choosing the next build to dispatch.

- [milestone-admission.md](../../milestone-admission.md): at most the
  profile's active milestones, in order.
- [plan-gate.md](../../plan-gate.md): only items in an owner-approved
  plan, with its exceptions and the platform preflight.

Routing, caps and the watcher stay in each runtime template.
