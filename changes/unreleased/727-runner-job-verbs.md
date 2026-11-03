---
type: added
issue: 727
pr: 736
date: 2026-11-03
box-skill: none (host entrypoint only; no template changes)
---

The host entrypoint (`scripts/crew-remote.py`) gains the forge-less runner's `job` and `result` verbs. `job` refuses a head that is not a commit in the host's project mirror and any command outside the closed set (`check-repo`, `tests` naming `scripts/test-*.py` files at that head, and one `evidence` capture). It then runs the commands in a detached worktree `jobs/<job_id>/wt/` in the background, with an env scrubbed of forge tokens, the SSH agent and profile values, and writes `jobs/<job_id>/result.json` with each command's exit code, duration and log path. `result` returns `running`, or the result with log tails capped. A retried `job_id` returns the first job, and jobs older than 7 days are removed.
