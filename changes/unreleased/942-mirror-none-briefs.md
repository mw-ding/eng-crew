---
type: added
issue: 942
pr: 998
date: 2026-11-04
box-skill: deferred to #140
---

The tmux `runtime.options.mirror = "none"` setting now reaches the
synthesizer brief and the protocol, slice B3 of #877. A new `<mirror-gate>`
render placeholder fills the synthesizer's mirror paragraph from the
setting: `live-copy` or unset renders today's standing-deferral paragraph
byte for byte, and `none` says instead that the mirror gate is `n/a` by
profile, to record `Mirror: n/a (profile)` on direct lands, to list no
mirror item in gate-status, never to wait on or ask for a mirror or
deferral, and to ignore `crew:needs-mirror`. The protocol §7 gate registry
row and No mirror hold bullet name the setting, the tmux runtime options
table gains the `mirror` row, and the tmux design section is no longer
marked proposed. The reviewer and coordinator briefs carry no mirror
instruction under either value, and Grok Bot wording is unchanged. The
setting supplies no approval or merge permission.
