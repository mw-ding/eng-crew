---
type: fixed
issue: 1398
pr: TBD
date: 2026-11-10
box-skill: none
---

A crew PR that turns `CONFLICTING` now reaches a builder without waiting for CI or a coordinator sweep: GitHub runs no `pull_request` CI on a conflicting PR, so approved PRs that conflicted after another land stalled with no checks. `mdstack poll` keeps each PR's last known mergeability and emits one `pr-conflicting` wake per head and conflict (an `UNKNOWN` read is no conflict and changes nothing), and `mdstack route` re-reads the PR and hands the builder lead one `merge-up` handoff, which the builder resolves with the existing merge-up note and delta review. A closed PR, moved head or resolved conflict consumes the wake; held, escalated, solo or lead-less work stays with the coordinator; a conflict that clears and returns hands off again.
