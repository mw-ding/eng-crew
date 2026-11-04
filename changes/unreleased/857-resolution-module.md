---
type: changed
issue: 857
pr: 868
date: 2026-11-04
box-skill: none (docs-only)
---

The profile's `## Validate` section moves verbatim into the new module
`docs/configuration/resolution.md` (M26 modular organization, batch 2): both
`crew-config.py validate` command variants, the `file:key: reason` problem
format and exit codes, the full rejection list and the install-time versus
run-time placeholder distinction, including the `resolve --install` check on
the effective profile; the profile keeps the `## Validate` heading and anchor
with a link to the module, and layers and precedence stay in the profile; no
rule, gate, marker or default changes.
