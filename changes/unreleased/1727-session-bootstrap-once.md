---
type: changed
issue: 1727
pr: 1762
date: 2026-11-12
box-skill: none
---

The session runtime doc's Upgrading section now names the one-time step for a session crew set up by `mdstack install` and a manual render: with no `install.json`, `mdstack upgrade` refuses it because adoption verifies tmux installs only, so run `mdstack bootstrap --project <absolute profile>` once (dry-run, then `--yes`) from the chosen install source and version, then upgrade as usual. Runtime behaviour is unchanged.
