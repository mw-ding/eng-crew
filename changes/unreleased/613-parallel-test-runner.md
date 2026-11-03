---
type: added
issue: 613
pr: 650
date: 2026-11-02
box-skill: none
---

`scripts/run-tests.py` runs the `scripts/test-*.py` suite in parallel (`-j N`, default the CPU count up to 8), prints per-file durations and the slowest files, shows the output of every failing file and exits non-zero on any failure. CI's `repo-guard` job runs the full suite with it in one step instead of one step per test.
