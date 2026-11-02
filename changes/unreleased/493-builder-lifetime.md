---
type: changed
issue: 493
pr: 523
date: 2026-11-01
box-skill: deferred to #140
---

Retain tmux builders after completion until their PR merges or closes, count only busy builders toward the cap, reclaim the oldest safely pushed idle builder when the physical band fills, and route later fix messages to a replacement automatically.
