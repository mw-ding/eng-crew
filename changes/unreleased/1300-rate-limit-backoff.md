---
type: fixed
issue: 1300
pr: TBD
date: 2026-11-08
box-skill: none
---

`mdstack watch` no longer spends a shared GitHub login's quota on every 5 s scan. Its `--source` commands now run at most once per `--source-interval` (default `runtime.options.poll_interval`, 60 s), and the next due time survives a re-arm. A rate-limited `gh` read in `mdstack poll` is no longer a non-transient failure that woke the coordinator and made the watcher exit on every poll. It is never retried: poll reads the reset from `gh api rate_limit` (60 s for a secondary limit), prints `rate-limited until <UTC>` and exits 75, and the watcher records an incident and holds its sources until that reset, at most an hour. Without `--once`, poll sleeps until the reset.
