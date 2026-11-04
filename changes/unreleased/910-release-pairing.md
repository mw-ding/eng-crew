---
type: fixed
issue: 910
pr: 921
date: 2026-11-04
box-skill: none (script and reference docs; no rendered doc changed)
---

`crew-config.py resolve` now refuses a half-declared release concern when an
external pack is loaded. A `[release]` table whose `[backends.release]` still
comes from the bundled default, while the pack's manifest declares release
capabilities, fails naming `[backends.release]` and the file to add it to,
so a release no longer silently runs the GitHub backend on a host without
GitHub. A `[backends.release]` naming the pack with no `[release]` table
fails naming `[release]`. Both halves present, neither present, an unrelated
pack and explicit GitHub bindings resolve as before. There is no opt-out.
