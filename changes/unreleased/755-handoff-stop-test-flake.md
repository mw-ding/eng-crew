---
type: fixed
issue: 755
pr: TBD
date: 2026-11-03
box-skill: none (test only)
---

Fix a flaky `test-crew-handoff.py` prompt-stop test that failed on `main` with an empty `handoff-stop.log`. The detached `handoff stopped` actor posts `stopped` and only then prints its `posted stopped` line, and its stdout is the log file, buffered until it exits. The test stopped waiting when the post appeared and could read the log before the line was flushed. It now waits for the actor's final log line, its completion signal, before checking the log and the post. `handoff stopped` itself is unchanged.
