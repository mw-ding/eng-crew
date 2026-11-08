---
type: fixed
issue: 1320
pr: 1405
date: 2026-11-08
box-skill: none
---

`scripts/docs-scan.py` no longer lets a branch or worktree scan overwrite the live docs scan. A new `--state-dir DIR` writes each `scan.json` under `DIR` in place of the profile's state dir, and a `--ref` scan now exits 2 unless `--state-dir` is given, so the live `<state-dir>/<owner>__<repo>/docs/scan.json` that the docs-pass timer and researcher read always holds the default-branch scan. The watcher's default-branch scan is unchanged.
