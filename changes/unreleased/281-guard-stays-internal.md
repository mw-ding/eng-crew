---
type: changed
issue: 281
pr: 1700
date: 2026-11-11
box-skill: none
---

The repo guard `scripts/check-repo.py` no longer ships in the release bundle. The secret-scan patterns, path glob and markdown scanning it shared with the install CLI now live in shipped `core/secret-patterns.py`, `core/path-glob.py` and `core/markdown-scan.py`, which `crew-config.py`, `docs-scan.py` and the guard all load, so detection and glob matching are unchanged. The bundle smoke test asserts the guard is absent and runs `check-markdown.py` and `docs-scan.py --help` from the bundle.
