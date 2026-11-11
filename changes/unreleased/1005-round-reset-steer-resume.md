---
type: fixed
issue: 1005
pr: 1656
date: 2026-11-10
box-skill: none
---

Reviewer rounds now restart after the coordinator's canonical `pass=steer cmd=resume` (or `cmd=cutover`) record, as protocol §5 and §9 already say. Before, `mdstack poll` reset the count only on a legacy `pass=resume` or `pass=cutover` marker, so after an owner-approved resume the pool dispatched a resumed fix head as round 4 instead of round 1. Legacy coordinator records still reset. With the profile, poll and reviewer dispatch derive the round the same way: they count only this runtime's reviewer verdicts and resets signed by its coordinator. Builder notes, other steer commands, ownership handoffs and other runtimes' records reset nothing. Merge-ups keep the round of the approval they renew. Round caps and gates are unchanged.
