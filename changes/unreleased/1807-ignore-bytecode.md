---
type: fixed
issue: 1807
pr: TBD
date: 2026-11-13
box-skill: none
---

Exclude Python bytecode caches from personnel test source snapshots so parallel bytecode writes cannot race the copy and fail CI.
