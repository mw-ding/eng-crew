---
type: added
issue: 349
pr: 744
date: 2026-11-03
box-skill: none
---

`docs/runtimes/multi-device.md` gains a runbook for adding a forge-less runner host. It covers the overlay, a copied and checked release bundle, a crew key forced to the `crew-remote.py` entrypoint, the user-level runner service, a `version` smoke test, the `forge = false` profile table, seeding with `crew host prepare` and a first `crew runner run --host`, plus how to remove a host. Until the remote `check` verb is built (issue #743), `crew host check` keeps a remote host `not ready`, so the runbook names the host with `--host`. The tmux runtime contract adds one row per kind of host: the primary (unchanged), a forge-less runner host (unchanged, with a local fallback) and a role host (not built).
