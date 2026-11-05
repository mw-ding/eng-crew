---
type: added
issue: 1025
pr: 1049
date: 2026-11-05
box-skill: none
---

`scripts/docs-scan.py`, the zero-model first stage of the project docs pass: for each `[docs] repos` entry it reads a local clone's git tree at the default-branch head (or a pinned `--ref`) and writes `<state-dir>/<owner>__<repo>/docs/scan.json` with the Markdown inventory (lines, docs index row and kind, status banner), essentials missing against the project doc set and `[docs] homes` (a `path#anchor` home needs that heading), design docs with no banner, banners whose Last checked is missing or older than `stale_days`, broken relative links and anchors, and docs over `size_budget`. Read-only: it reads git objects only and writes nothing but each scan.json; with no `[docs]` table it does nothing.
