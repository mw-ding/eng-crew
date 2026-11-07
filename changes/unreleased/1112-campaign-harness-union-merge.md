---
type: changed
issue: 1112
pr: 1113
date: 2026-11-06
box-skill: none
---

`docs/campaign-harness.md` is marked `merge=union` in a new `.gitattributes`, so a local merge-up of two M25 campaign PRs that append scenario lines or notes sections at the same place keeps both sides with no manual resolution. The `.gitattributes` header and a contributor note in the page say union merge suits append-only edits only (a reorder or rewrite still needs a normal review of the merged result) and that GitHub's server-side mergeability check is not documented to honour the attribute, so the builder's local merge-up is still needed. `scripts/check-repo.py` gains an `attributes` check that fails when the line goes missing.
