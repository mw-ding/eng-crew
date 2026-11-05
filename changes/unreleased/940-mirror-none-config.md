---
type: added
issue: 940
pr: 971
date: 2026-11-04
box-skill: none (script only; no docs/protocol.md or rendered template change)
---

`crew-config.py` accepts an optional tmux `runtime.options.mirror`
(`live-copy` or `none`, default `live-copy`), slice B1 of #877. `validate`
and `resolve` refuse any other value, refuse the key under Grok Bot
(unknown key), and refuse `mirror = "none"` together with a
`mirror_deferral` other than `"none"`, since an install with no live copy
has nothing to defer. A team file's `[repos.<name>]` section may set it.
`resolve` now prints `runtime.options.mirror = "live-copy"` for an unchanged
tmux profile; nothing reads the value until B2 (#941) and B3 (#942) land.
