---
type: added
issue: 183
pr: 513
date: 2026-11-01
box-skill: none
---

Metrics refresh records builder precheck markers and reports rounds per PR, request-changes verdict rate and mean PR-to-merge time by repo and recorded versus unrecorded precheck cohort. Counts and empty denominators are explicit; unrecorded checks do not establish that the profile switch was disabled. Offline fixtures cover marker parsing, duplicate verdicts, closed unmerged PRs and the CSV/Markdown CLI output. No gate thresholds changed.
