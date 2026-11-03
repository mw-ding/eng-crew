---
type: fixed
issue: 607
pr: 608
date: 2026-11-02
box-skill: none
---

CI's `repo-guard` job timeout is raised from 10 to 25 minutes. The suite had grown to about 10 minutes, so main and PR runs were cancelled at the limit with no failing test, and nothing could land. Splitting the job into parallel jobs is left as a follow-up.
