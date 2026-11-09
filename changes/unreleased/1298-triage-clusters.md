---
type: added
issue: 1298
pr: TBD
date: 2026-11-08
box-skill: none
---

Triage sweeps now group related but distinct open issues into clusters. The new `scripts/triage-clusters.py` places each open issue in at most one cluster by deterministic keys (failure class, Source, `Depends on` target, path prefix), keeps each slug stable across sweeps, lets the model add members with a one-line reason, and counts a cluster proposal (a tracking issue or a whole-cluster milestone move) once toward the noise cap. The researcher's sweep brief posts one `pass=triage-cluster` record per new or changed cluster on the day's log, labels members `cluster:<slug>` in `apply` mode, and never closes or merges a member. `scripts/triage-metrics.py report` adds cluster counts, and `docs/triage.md` gains a Clusters section.
