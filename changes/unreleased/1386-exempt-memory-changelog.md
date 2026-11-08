---
type: fixed
issue: 1386
pr: 1397
date: 2026-11-08
box-skill: none
---

`scripts/check-changelog-pr.py` now exempts `memory/**`, so a memory PR, which `docs/memory.md` says changes only `memory/`, passes the changelog check without a fragment. A PR that changes `memory/` together with other content still needs one. `docs/memory.md` and `CONTRIBUTING.md` say so.
