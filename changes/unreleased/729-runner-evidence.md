---
type: added
issue: 729
pr: 742
date: 2026-11-03
box-skill: none (evidence helper and docs; no Grok Bot template change)
---

`scripts/evidence-cli.py --runner <job_id>` renders a stored `crew runner` result as a capture: the header names `runner:<host>/<job_id>` and the head sha, and the text block lists each command's exit code and log tail with a `result: pass|red` line. It refuses a result whose head is not the checkout's HEAD. `--runner-fallback "<line>"` adds the runner's `ran locally` line to a local capture. `crew runner` now stores the command set it ran so the capture's `sh` block can name it. `docs/verification.md` adds a row: a runner capture at the PR head counts as a local run of the same commands, a capture at another head does not, and PR CI stays the full-suite gate.
