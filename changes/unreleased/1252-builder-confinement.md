---
type: fixed
issue: 1252
pr: 1707
date: 2026-11-11
box-skill: none
---

A builder run can no longer remove another run's working copy when its launch is confined (#1252, M47 B5). Spawn gives each builder its own Git metadata (a local copy borrowing the shared checkout's objects read-only) instead of a linked worktree, and Codex in `safe` or `auto` runs it under an OS write sandbox whose writable roots are only that copy and the state dir (`/tmp` and `$TMPDIR` dropped, `TMPDIR` moved into the copy). The new `runtime.options.confinement` (`enforce` or `off`, default `off`) refuses an unconfined builder spawn or restart under `enforce`, including a host where `codex sandbox -- true` fails (a launcher that already sandboxes Codex nests the sandbox); under `off` the run record marks it unconfined and `mdstack doctor` warns. `mdstack migrate` moves each builder copy with the crew.
