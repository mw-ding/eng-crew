---
type: changed
issue: 1223
pr: 1263
date: 2026-11-07
box-skill: none
---

The GitHub backend's capability declaration moves from `packs/github/manifest.toml` to `connectors/github/manifest.toml`, beside the GitHub repository checks, so the GitHub connector declares every concern operation from `connectors/github/`. `crew-config.py resolve` and `validate` and `crew-render.py` read built-in backend manifests from `connectors/<name>/`; profiles resolve to the same values and provenance (`pack:github`), and briefs render unchanged. For one release `packs/github/manifest.toml` stays as a copy of the connector's manifest, held equal to it by `test-compat-shims.py`, so org packs and tools that name the old path keep working. External org packs load as before through `--pack-manifest`, `--org-profile` or `paths.pack`.
