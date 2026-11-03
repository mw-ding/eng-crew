---
type: added
issue: 622
pr: TBD
date: 2026-11-03
box-skill: none
---

The crew scheduler ranks both pools' demand from a schedule snapshot in one list: the eight finish-before-start classes of the scheduling design, then milestone order, `Depends on` critical path (open items waiting, directly or transitively) and age. It is a pure function with no command yet and changes no admission.
