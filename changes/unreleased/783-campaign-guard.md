---
type: added
issue: 783
pr: 810
date: 2026-11-04
box-skill: none (internal campaign script and doc; no template or box-skill changes)
---

`scripts/campaign-guard.py` is the M25 campaign harness contract (25.01). `manifest` writes a run manifest that pins the sandbox repo, profile (path and sha256), source checkout SHA, installed release id, tmux session, state/worktree/live roots and an outside-sandbox sentinel. `check` refuses with exit 2, before any mutation, when the sandbox names the production repo or session, a sandbox root equals or nests with a production root, a root is still a placeholder, or a pin drifted. `sentinel` re-hashes the sentinel after teardown. `docs/campaign-harness.md` documents the contract, including the retained-work cleanup check.
