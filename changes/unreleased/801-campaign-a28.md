---
type: added
issue: 801
pr: TBD
date: 2026-11-06
box-skill: none (internal campaign harness, fixture and doc; no template or box-skill changes)
---

The M25 campaign gains the A28 scenario spec (ownership, two-team handoff and detached teardown) in `scripts/fixtures/campaign/` (25.19). It runs two sandbox teams on one repo on real sandbox tmux at level a. It covers one writer with an untrusted claim ignored, drain then abort, a lost offer response retried to one post, a partial reconcile that holds the diverged set and flags the stale in-transit marker, kept run and rule difference, a lost ack response acked once, `crew handoff stopped` typed in the outgoing session posting `stopped` only after the session and watcher are gone while keeping unlanded work, a return in stop mode that posts nothing on a change, a mid-way takeover reusing the handoff id, and the detached stop repeated 20 times under parallel load with counts. The sandbox `gh` stub now answers `gh api` from a scenario path map that keeps posted comments, with injected lost posts and a post-time probe.
