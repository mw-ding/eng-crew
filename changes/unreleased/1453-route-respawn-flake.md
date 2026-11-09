---
type: fixed
issue: 1453
pr: TBD
date: 2026-11-08
box-skill: none
---

`test-crew-route.py`'s queued researcher `done:` test (#1092) no longer flakes when both researcher spawns land in the same UTC second. The fake tmux reports no pane identity, so the two runs differed only by their second-granularity `start` and the test's "different run" assertion could see equal identities. The test now backdates the first run's recorded `start` before building the queued `done:` from it. Real tmux gives each pane a unique id, so product behaviour is unchanged.
