---
type: fixed
issue: 1433
pr: 1511
date: 2026-11-09
box-skill: deferred to #140 (profile mirror_deferral)
---

A release cut no longer lands on a stale merge ref. `mdstack train check` gains a `release-cut` gate that blocks a cut PR (its diff adds a new version heading to the CHANGELOG) until its head contains the current default branch, so update-branch re-runs `release.yml` `validate` there and the `lone_pr_land = "direct"` waiver never takes a stale cut. While a cut PR is open, the state-permission gate in `train check` and `train land` holds every other PR that adds a `changes/unreleased/` fragment until the cut lands, and an unreadable open-PR list or CHANGELOG patch holds too (a cut whose patch is missing is blocked, never read as a non-cut). This replaces the coordinator's hand-posted `hold-until` that 7.1.0 needed and 7.2.0 lacked (main-red #1432). `docs/release.md` (Cut freeze), protocol §7, the synthesizer pre-check and the coordinator brief describe the rule.
