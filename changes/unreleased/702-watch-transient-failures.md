---
type: fixed
issue: 702
pr: 708
date: 2026-11-03
box-skill: none (tmux CLI only)
---

Stop transient GitHub failures from waking the coordinator. `crew poll` retries its PR and issue list reads when one fails with a 5xx, timeout or connection reset (three retries, 1, 2 and 4 s apart) and exits 75 (`EX_TEMPFAIL`) if the failure persists. `crew watch` records a source cut off at `--source-timeout` (now 60 s by default) or exiting 75 as a line in `wake/incidents.jsonl` instead of waking, and sends one `source-failing` wake with the count after `--source-failures` (default 3) in a row; a clean run resets the count. The watcher also re-execs itself in place, before it queues or routes a scan's wakes, when `scripts/crew`, `crew.d/*.py` or `crew-*.py` change on disk, so a crew-home update no longer leaves an old process validating new profile keys (folds in #703).
