---
type: added
issue: 941
pr: TBD
date: 2026-11-04
box-skill: none (script only; no docs/protocol.md or rendered template change)
---

`crew train check` and `crew train land` read the tmux
`runtime.options.mirror` setting, slice B2 of #877. With `mirror = "none"`,
the mirror gate reports `status=pass reason="n/a: profile mirror = none"`
for every PR, before #911's repo and path applicability and whether or not
`crew:needs-mirror` is present; every other hold still blocks. The train
merge record then says `- Mirror: n/a (profile).` instead of
`- Mirror deferral used: <value>.`, and `--mirror-deferred` still refuses
because no deferral can be set alongside `none`. The pass is diagnostic, not
an approval or grant. An unset or `live-copy` profile keeps today's check
output and merge record byte-identical.
