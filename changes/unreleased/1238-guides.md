---
type: added
issue: 1238
pr: TBD
date: 2026-11-07
box-skill: none
---

Four guides under `docs/guides/` give new and existing installs a clear path. `getting-started.md` covers the one-command bootstrap into the home root, the first `mdstack up`, talking to the team head (`ash`, the `cto` seat) and adding an on-demand role with `mdstack up <role>`. `connectors.md` shows picking one connector per concern and setting up the knowledge connector: the role names the source in git, the page pointer lives in the private config, and the token stays in an environment variable. `pack-authoring.md` covers the pack format and `pack.toml`, the plug-in points, wiring with `paths.pack` and `mdstack pack list`, and the conformance kit `mdstack pack test`. `migration.md` covers the move from the old layout and CLI name: the ordered steps, the `crew` → `mdstack` shim kept for one release, the 6.0.0 old-path-to-module table and the shim removal in 7.0.0, and pack updates. The docs index, runbook and deliverables manifest list them. Navigation only; no rule, gate, marker or default changes.
