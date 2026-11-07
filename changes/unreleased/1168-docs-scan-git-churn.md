---
type: fixed
issue: 1168
pr: 1169
date: 2026-11-06
box-skill: none
---

`scripts/test-docs-scan.py` no longer flakes when git's background maintenance creates or removes a transient file such as `.git/objects/maintenance.lock` during the writes-only-scan.json test: the before/after snapshot skips `.git/objects/**` and lock files under `.git/`, and the fixture repos turn off auto-maintenance (`gc.auto=0`, `maintenance.auto=false`). A regression test proves the comparison ignores that churn and still catches an extra work-tree write.
