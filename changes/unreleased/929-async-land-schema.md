---
type: added
issue: 929
pr: TBD
date: 2026-11-04
box-skill: none (scripts and reference docs; no rendered template change)
---

Pack manifests accept an optional `[land]` table for an asynchronous land
(#873 slice B1): `mode` (`sync` or `async`, default `sync`) and the booleans
`opens_draft`, `serializes` and `tests_against_tip`. The `change` concern
accepts the conditional operations `publish` and `land-status`, which a
`sync` manifest leaves out. `crew-config.py validate` rejects `async`
without `change.land-status`, `opens_draft` without `change.publish`, and the
booleans under `sync`; `resolve` repeats those checks on the effective
capabilities, refuses `async` on a runtime without an async binding (every
runtime but tmux) and prints the declared `land.*` keys as pack metadata.
New tmux options `land_poll_interval` (default 60) and `land_timeout`
(default 3600, at least the interval) are validated. Nothing reads the
schema yet, and GitHub and every unchanged manifest stay `sync` with
unchanged output, apart from the two new option lines in `resolve`.
