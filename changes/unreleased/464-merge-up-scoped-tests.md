---
type: changed
issue: 464
date: 2026-11-02
---

Builders running a merge-up (a push whose only new commit merges the default branch) now run `check-repo.py` and only the `scripts/test-*.py` covering the conflicted files, and list them with the reason in the merge-up note; PR CI and the recheck pass cover the rest. Normal builds and fix rounds keep the full local run.
