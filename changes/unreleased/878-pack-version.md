---
type: added
issue: 878
pr: 919
date: 2026-11-04
box-skill: none (scripts and reference docs; no rendered template change)
---

Pack manifests accept an optional SemVer `pack.version` for the pack's own
release, distinct from the `eng_crew_version` pin. `crew-config.py validate`
checks its shape, `resolve` prints it as pack metadata with `pack:<name>`
provenance, bootstrap and upgrade record it in `install.json` (an upgrade
that changes only the pack version no longer reports `no changes`), and
`crew doctor` shows it. Without it, output and records are unchanged. A
`paths.pack` directory without `profile.toml` now also supplies its
`manifest.toml` to `resolve`.
