---
type: added
issue: 1411
pr: 1673
date: 2026-11-11
box-skill: none
---

Tests only: two regression cases in `dev/tests/core/test-crew-pack.py` resolve a `pack.toml` plug-in pack through project `paths.pack` discovery, never `--pack-manifest`. With its optional `profile.toml` removed, the pack still provides its connector, harness and skill, layers resolve as `core, default, pack, project` with the pack's environment defaults, and the flavor falls back to the core default `standard`. With no backend render map for its tracker connector, `resolve` keeps the default numeric item and change ids and still refuses a native string control item; adding the map on the same path makes it accepted. No behaviour changes.
