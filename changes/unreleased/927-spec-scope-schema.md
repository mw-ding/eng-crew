---
type: added
issue: 927
pr: TBD
date: 2026-11-04
box-skill: none (scripts and reference docs; no rendered template change)
---

`crew-config.py validate` accepts two optional keys from the #398 spec grant
design: a `[spec]` table whose `paths` globs replace the default
`["docs/specs/**"]`, and `runtime.options.merge_grant_scope` (`approved`,
`spec`), which refuses unknown values, `[]` and `spec` with
`merge_grant = "none"`. Team files allow `spec` under `[team]` and both keys
in a `[repos.<name>]` section. No gate reads either key until slice B2;
without them, resolution and behaviour are unchanged.
