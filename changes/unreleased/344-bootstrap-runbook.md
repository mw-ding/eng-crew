---
type: changed
issue: 344
pr: TBD
date: 2026-11-01
box-skill: none
---

The new-repo runbook now leads with crew bootstrap preview and confirmed apply, verifies its recorded state before completing wiring, and retains manual profile, render and state setup as the fallback. It distinguishes the current core from pending automation and keeps routine creation, tmux startup and the smoke test explicit.
