---
type: changed
issue: 319
pr: 477
date: 2026-11-01
box-skill: none
---

The tmux runtime reads role bands, passes, names, caps, event consumers and spawn metadata from the engineering role registry, preserving existing behavior and leaving profile and renderer migration to the next slice. Bootstrap and offboarding test bundles include the role registry, and release bundle tests verify it is shipped with the CLI.
