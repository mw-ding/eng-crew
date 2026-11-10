---
type: added
issue: 1557
pr: TBD
date: 2026-11-09
box-skill: none
---

Role posts that report a pass now end with a usage line just above the signature, for example `Run: 23m 10s · 1.24M in (1.1M cached) / 38.2k out · claude-opus-5-5 (high)`. New `scripts/run-usage.py` prints it from a run record (or `--engine`, `--dir` and `--start` for the coordinator): wall-clock time from the run start to now, token totals and the model. Harness adapters gain an optional `usage(directory, start)` reader of their local session log; Claude Code (transcript JSONL, each streamed message counted once, cache reads as cached) and Codex (cumulative `token_count` events, less any total before the start) ship one, and any other harness prints `tokens n/a`, never an estimate. A new shared fragment `templates/policy/shared/usage-line.md` puts the instruction in the tmux and session builder, reviewer, synthesizer and coordinator briefs and the tmux researcher brief. The figures are informational only: no gate, verdict, flavor or scheduler decision reads them, markers, signatures and effort attribution are unchanged, and no path or credential is printed. `docs/roles.md` (new Usage line section) and `docs/flavors.md` record the owner's reversal of "off the record" for role posts.
