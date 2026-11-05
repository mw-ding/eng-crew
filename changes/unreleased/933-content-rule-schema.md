---
type: added
issue: 933
pr: 976
date: 2026-11-04
box-skill: none (config tool and reference docs only; no rendered template change)
---

`crew-config.py validate` and `resolve` accept optional
`[[sensitive.content]]` rules (#879 slice B1): unique nonempty `name`, a
`pattern` that compiles as a Python regex, a nonempty `reason` and optional
repo-relative `paths` scope globs. A layer replaces the whole array. Diff
matching is not in yet, so `sensitive` exits 3 (classification incomplete)
on a profile that declares content rules; profiles without them classify
exactly as before.
