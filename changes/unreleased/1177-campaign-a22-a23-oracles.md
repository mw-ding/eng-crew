---
type: fixed
issue: 1177
pr: TBD
date: 2026-11-08
box-skill: none
---

Campaign scenario A22 no longer fails on a run id with capital letters: its duplicate-key check now expects the lowercased `source:` key that the triage scan writes, so `m25f-A22` passes like `m25f-a22`. A new `test-campaign-run.py` case runs A22's seeded forge through the real triage scan and its oracle for both run ids. A23's note on automatic pick no longer says the host entrypoint lacks a `check` verb, which #1117 built. It now says why pick still falls back in the sandbox: the check reports the runner down, and the runner service cannot start there because it opens tmux on the default socket, which the sandbox shim refuses.
