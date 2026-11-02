---
type: added
issue: 531
pr: TBD
date: 2026-11-01
box-skill: deferred to #140
---

Long-lived reviewer lead in reserved window 3 owns review, validation, recheck escalation and terminal reclaim through durable serialized handoffs, cap/load/suite admission and one-restart supervision. Replay recovers missing validation and deduplicates fresh passes while preserving synthesizer verdict portability. Failed Actions jobs with no started steps are infrastructure incidents: validation may proceed, but green CI remains required for landing. Scaling, replay and recovery fixtures accompany the change.
