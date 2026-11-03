---
type: fixed
issue: 719
pr: 724
date: 2026-11-03
box-skill: none (tmux CLI only; no template changes)
---

A finished reviewer pass (review with no successor, validate, recheck) is reaped once even when its PR has merged, closed, moved to a new head or been held. Since S7 (#625) the reviewer lead saves a `crew kill` reclaim as the worker's `done:` completion, and `crew route` returned early on such a PR without reaping, so finished validate workers kept their run records and filled the reviewer cap. `crew schedule summary` now ends with `terminal N <windows>`, naming reviewers that wrote their final `done:` but still hold a slot.
