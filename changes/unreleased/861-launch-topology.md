---
type: changed
issue: 861
pr: 890
date: 2026-11-04
box-skill: none (docs-only)
---

The profile's `tmux` launch topology (`[runtime.options.launch]`) moves
verbatim into a new `## Launch topology` section of
`docs/configuration/runtime-options.md` (M26 modular organization, batch 2):
the absent-table fallback, the four-row key table with every value, default
and refusal constraint, the unchanged window-name and tag statement and the
complete TOML example. Only relative-link prefixes and the `launch` row's
pointer change; the profile keeps the `` ### `[runtime]` `` heading and anchor
with direct links to runtime keys and shared options, `tmux` options and the
launch topology; no rule, gate, marker or default changes.
