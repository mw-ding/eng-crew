---
type: changed
issue: 1691
pr: TBD
date: 2026-11-11
box-skill: none
---

The portable spec opens M47 (installs and working copies): seven planned builds with their dependencies (B1 and B2 before B3, B5 before B6), the settled memory-source, cleanup and deferred-provider decisions with #316's AC4 revised, and the enforcing boundary for #1252: per-run Git metadata plus an OS write sandbox, with unsupported configurations refused under `runtime.options.confinement = "enforce"`.
