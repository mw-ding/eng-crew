---
type: added
issue: 799
pr: 1094
date: 2026-11-06
box-skill: none (internal campaign fixture, sandbox stub and doc; no template or box-skill changes)
---

The M25 campaign gains the A22 scenario spec (triage scan, shadow proposals and calibration) in `scripts/fixtures/campaign/` (25.17). It runs on real sandbox tmux at level a. The poll scan skips placed, flavored, recorded, log and pull-request items, records a malformed item, hints an exact duplicate and wakes a P0 once. The sweep timer skips an empty queue and catches up when overdue. Shadow records cite what they used, extract a card once and apply nothing. The owner's sample answers are recorded, and the ten-sample bar is met at 8 of 10 and frozen into the eval set, while mode stays shadow with no `crew:ready`. The noise cap, the rejection cooldown and repeat sweeps hold. The sandbox `gh` stub now answers an `issue list --state S` call from its own file.
