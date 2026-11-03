---
type: added
issue: 634
pr: TBD
date: 2026-11-03
box-skill: none (config tooling and docs; no template changes)
---

Team files: one `<config-home>/teams/<team>.toml` holds a crew's team-only settings under `[team]`, with `pack`, `personas` and `accounts` shorthands. Each repo gets a small `[repos.<name>]` section that may set only an allowlist: repo, default branch, precheck, sensitive paths and landing overrides. A project reference `<file>#<repo>` resolves as core < default < org < team < repo. A legacy `crew.toml` resolves byte-identically. `crew up --team <file>` starts one session and coordinator for every repo, with a render per repo under `<state_dir>/<team>/<owner>__<repo>`. docs/profile.md gains a migration note from two `crew.toml` files to one team file.
