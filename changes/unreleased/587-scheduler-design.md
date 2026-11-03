---
type: added
issue: 587
pr: TBD
date: 2026-11-02
box-skill: none
---

Added the crew scheduler design (docs/scheduling.md): one crew-wide `crew schedule decide` that both pool leads call, built from observable crew demand, item priority, worker state, machine load, memory pressure, gateway errors and owner presence. It ranks finishing work before new builds, moves a crew-wide concurrency target between load watermarks with a ramp limit instead of on/off gates, keeps one slot per pool so reviews cannot starve, sequences builds that touch the same files, records every admit, defer and reclaim with reasons, and lists eleven follow-up build issues. Design only: admission is unchanged until those land.
