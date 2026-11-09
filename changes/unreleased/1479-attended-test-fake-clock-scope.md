---
type: fixed
issue: 1479
pr: 1481
date: 2026-11-08
box-skill: none
---

`dev/tests/scripts/test-campaign-attended.py` no longer fails on Linux CI with "the receipt is not asked once the snapshot changed". Its fake clock patched `time.sleep` on the shared `time` module, so the changed-window test's fake sleep, which rewrites the tmux window list, also ran inside `subprocess.run`'s timed wait loop while a pre-sleep A26 step's child was being reaped. That rewrote the window list before the before-sleep snapshot was taken, so both snapshots matched. The tests now give `campaign-attended.py` its own fake `time` namespace, so other callers keep the real clock.
