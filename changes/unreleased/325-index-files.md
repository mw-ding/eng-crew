---
type: changed
issue: 325
pr: 362
date: 2026-11-01
box-skill: deferred to #140
---

Conflict-free index files, part 2 of #325 (part of #110). The inventory table in `docs/deliverables.md` is now generated from `scripts/deliverables.txt` (one row per manifest row; the manifest gained an optional Why column), and `python3 scripts/check-repo.py --fix` rewrites it. `scripts/deliverables.txt`, `scripts/required-docs.txt` and the `docs/README.md` rows are sorted, so a new entry lands at its own place instead of the end of the file, where every PR appended. The new `check-repo.py` check `index` (rules `index-stale`, `index-order`, `docs-index`) fails on a stale table, an unsorted file, a duplicate row, or a deliverable doc missing from the index. CONTRIBUTING.md and the worker brief rules in `docs/roles.md` gain the rule: no new shared append-hotspot files, one file per item or a generated aggregate. `test-check-repo.py` proves that two branches that each add a script, a doc and their index rows merge with no conflict, and that the same additions appended at the end of the files conflict.
