---
type: fixed
issue: 542
pr: 562
date: 2026-11-02
box-skill: none
---

Builder lead records admission deferrals locally and reports only actionable blocks to the coordinator, deduplicating identical notifications across restarts. The router consumes deferred status wakes without coordinator action.
