---
type: fixed
issue: 369
pr: TBD
date: 2026-11-13
box-skill: none
---

Plain mdstack down removes coordinator scratch files after a successful stop,
including when no session remains, while preserving them during maintenance
stops and refusals. Remove an unused import from the coordinator guard.
