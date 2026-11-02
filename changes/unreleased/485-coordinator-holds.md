---
type: fixed
issue: 485
pr: TBD
date: 2026-11-01
box-skill: none
---

Merge train gates recognize hold-until dependencies only in coordinator posts,
so quoted test strings in reviewer, builder and synthesizer posts no longer
block landing. Missing or unreadable dependencies produce a clear blocked
gate result instead of an unhandled lookup error.
