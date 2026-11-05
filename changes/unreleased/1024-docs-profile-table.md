---
type: added
issue: 1024
pr: 1044
date: 2026-11-05
box-skill: none
---

Profile: an optional `[docs]` table for the project docs pass (`enabled`, off by default, `interval_days`, `repos`, `stale_days`, `size_budget` and `homes`), checked by `crew-config.py validate` (types, minimums, non-empty `owner/name` repos, `homes` keys limited to the five essential docs with repo-relative `path` or `path#anchor` values) and given its defaults by `resolve` only when the table is present. The essential doc set and the status banner convention moved from the project docs design into a new `docs/project-doc-set.md` reference module the profile links.
