---
type: fixed
issue: 1344
pr: 1706
date: 2026-11-11
box-skill: none
---

`mdstack bootstrap --project <team file>#<repo>` bootstraps the selected repo of a multi-repo team file instead of proposing a literal `#<repo>` profile: the reference reaches resolve, doctor, render, the `--version` release source and `install.json`, the team file is read and copied as TOML, repo-local pointers and excludes go in the selected repo's `paths.checkout`, uninstall cleans them there, and `mdstack upgrade --version` follows such a recorded install.
