---
type: changed
issue: 165
pr: 290
date: 2026-10-31
box-skill: none
---

Resolver as a function (structural, no behaviour change):
`scripts/crew-config.py` exposes `resolve_profile(project,
org_profile=None)`, which returns the merged profile, per-key provenance,
the problems and the layer names. The `resolve` CLI prints from it, and
`scripts/crew-render.py` calls it directly instead of running
`resolve_main` and parsing its printed `key = value  # layer` lines. The
`resolve` output (stdout, stderr, exit code) and the render goldens are
unchanged.
