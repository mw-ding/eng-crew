---
type: fixed
issue: 369
pr: 1831
date: 2026-11-13
box-skill: none
---

Plain mdstack down removes regular coordinator scratch files after a successful stop,
including when no session remains, while preserving them during maintenance
stops and refusals and retaining symlinks. Remove an unused import from the coordinator guard.
