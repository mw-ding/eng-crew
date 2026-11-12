---
type: changed
issue: 1727
pr: 1762
date: 2026-11-12
box-skill: none
---

The session runtime doc's Upgrading section now names the one-time step for a session crew set up by `mdstack install` and a manual render: with no `install.json`, `mdstack upgrade` refuses it because adoption verifies tmux installs only, so bootstrap once: with dispatch paused, move the manual render and any state `mdstack` link, `VERSION` and `config.toml` into a backup (bootstrap refuses files it does not own), run `bootstrap --project <absolute profile>` from the chosen release bundle's own `cli/mdstack` (dry-run, then `--yes`) to re-render, re-link and write `install.json`, then diff against the backup and upgrade as usual. Runtime behaviour is unchanged.
