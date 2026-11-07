---
type: changed
issue: 1183
pr: 1259
date: 2026-11-07
box-skill: none
---

Each session backend is now one adapter module, `scripts/session.d/<name>.py`, declaring its CLI, its place among the choices and its capabilities (`doorbell`, `reload`, `dead-keeps-pid`) beside its create, attach, doorbell, identity and state, window, kill and reload operations. `scripts/crew-session.py` discovers the modules and derives the `runtime.options.session_backend` choices and the active backend; `crew doctor` takes the CLI to look for from the adapter. The OS process helpers move out of the tmux adapter into `scripts/crew-proc.py`. `crew send`, `crew watch`, the liveness probe, the merge lock's owner check, `crew up`'s attach hint and `crew upgrade` now branch on declared capabilities and operation results instead of `name == "herdr"` or raw tmux verbs, so adding a backend means adding its module and tests. Unknown activity, unavailable probes, failed delivery and surviving processes keep their ambiguous or refusal results, and tmux and herdr behave as before.
