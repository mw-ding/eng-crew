---
type: fixed
issue: 817
pr: TBD
date: 2026-11-04
box-skill: none (internal campaign scripts and doc; no template or box-skill changes)
---

The M25 campaign harness can no longer reach a tmux server outside its sandbox. An inherited `$TMUX` beats `TMUX_TMPDIR`, so a bare sandbox `tmux kill-server` from a crew pane killed the owner's default server. `scripts/campaign-sandbox.py setup` now installs a `state/bin/tmux` shim that pins every call to the sandbox socket with `-S`, drops `TMUX` and `TMUX_PANE`, and refuses `-L` or a foreign `-S`. `teardown` kills the sandbox session on that socket. `scripts/campaign-run.py` puts the shim first on the scenario `PATH`, strips `TMUX` and `TMUX_PANE`, and runs a decoy session on a throwaway socket, exported as `TMUX`. A scenario that kills the decoy FAILs and stops the run.
