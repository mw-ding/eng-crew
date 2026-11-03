---
type: fixed
issue: 610
pr: TBD
date: 2026-11-02
box-skill: none
---

The release workflow's `validate` job timeout is raised from 10 to 25 minutes, matching CI's `repo-guard`. It runs the same full suite, so the v3.2.0 cut's release run was cancelled at the 10-minute limit with no failing test, and the release could not publish. No other workflow job runs the full suite.
