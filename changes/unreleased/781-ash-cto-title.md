---
type: changed
issue: 781
pr: 1279
date: 2026-11-07
box-skill: none
---

Ash's default display title is now `CTO`, so a fresh default render signs
coordinator posts `— 🔥 Ash (CTO) · <harness> · <model>`. The pipeline role
id `coordinator`, the `<CoordinatorBot>` / `<CoordinatorTitle>` placeholders
and coordinator templates are unchanged; a profile that sets
`identities.coordinator.title` keeps its own value. Away-record parsing now
matches the resolved coordinator title instead of a hardcoded `(Coordinator)`,
and still accepts that legacy sign on records posted before the change.
