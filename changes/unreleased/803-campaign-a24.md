---
type: added
issue: 803
pr: 1105
date: 2026-11-06
box-skill: none (internal campaign fixtures and doc; no template or box-skill changes)
---

The M25 campaign gains the A24 (release cut, bundle and exact-SHA CI and approval gate) scenario spec in `scripts/fixtures/campaign/` (25.21). At level a it cuts a release in a bare clone of the source: the cut PR consumes the fragments and lands as a merge commit. The dry run then detects the cut, validates it and bundles that exact SHA with a checked `SHA256SUMS`. A non-cut push is a green no-op. Each refusal case refuses: a wrong or missing actor, approval at an earlier head or the merge commit, a non-owner marker, a non-cut or missing merged PR, missing, pending, red, cancelled, skipped or timed-out CI at the landed SHA, and a duplicate tag. A retry after green CI passes. No tag or release is written. The commit release id binding cuts and checks with the profile's paths.
