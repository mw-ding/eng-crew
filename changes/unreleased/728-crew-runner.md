---
type: added
issue: 728
pr: 739
date: 2026-11-03
box-skill: none (tmux CLI and the tmux builder brief; no Grok Bot template change)
---

`crew runner run --head <sha> [--host <h>] -- check-repo test-*.py...` runs the targeted local set on a forge-less host. It picks `--host`, else the ready forge-less host with the lowest load against `max_runs`, seeds a bundle of the head, starts a `job`, polls `result`, stores the result under `$CREW_STATE/runner/<job_id>/` and prints `runner:<host>/<job_id> head=<sha>` with each command's exit code. A transport failure on 3 calls in a row, or a `refused` or `failed` reply, runs the same commands locally and prints `runner: <host> <reason>; ran locally`; a late remote result is discarded. With no forge-less host it runs locally. A red remote command is a red run, not a fallback. `crew runner logs <job_id> [<command>]` prints a job's log tails. The tmux builder brief names `crew runner` as an option for the targeted local set.
