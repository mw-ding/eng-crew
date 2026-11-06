---
type: added
issue: 787
pr: 1066
date: 2026-11-05
box-skill: none (internal campaign scripts, fixtures and doc; no template or box-skill changes)
---

The M25 campaign gains the A03 (tmux lifecycle), A04 (wake, route and watcher) and A05 (liveness and recovery) scenario specs in `scripts/fixtures/campaign/` (25.05). They run on real sandbox tmux at level a. The sandbox now writes its profile into the sandbox clone, as `crew spawn` takes the repo from the profile's checkout, and installs engine stubs plus a scriptable fake forge (`gh`) in `state/bin`. `campaign-run.py` expands `{source}` and passes the stub logs and the fake forge directory to each step. A03 tears down with `kill-session` on the sandbox socket, never `kill-server` (#817).
