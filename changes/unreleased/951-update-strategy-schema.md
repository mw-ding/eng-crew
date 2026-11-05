---
type: added
issue: 951
pr: 982
date: 2026-11-04
box-skill: none (scripts and reference docs; no rendered template change)
---

Pack manifests accept an optional `[strategy]` table for the update from base
(#874 slice B1): `update_from_base` (`merge` or `rebase`, default `merge`) and
the boolean `retains_prior_heads`. `crew-config.py validate` rejects `rebase`
unless `retains_prior_heads = true`, and `retains_prior_heads = true` under
`merge`; `resolve` repeats both checks on the manifest of the backend bound to
`change` and prints the declared `strategy.*` keys as pack metadata. Nothing
reads the schema yet, and GitHub and every unchanged manifest stay `merge`
with unchanged `resolve` output.
