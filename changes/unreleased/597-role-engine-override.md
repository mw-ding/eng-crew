---
type: added
issue: 597
pr: 599
date: 2026-11-03
box-skill: none (profile schema and spawn engine choice; no box skill change)
---

Add an optional per-role engine override, `[engines.roles.<role>] order = [...]`, for spawned roles. It replaces the tier order for that role's workers (the tier still sets effort), reviewer independence still filters it, and `validate`, `resolve`, `crew doctor` and `crew up` read it.
