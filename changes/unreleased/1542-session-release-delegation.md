---
type: fixed
issue: 1542
pr: TBD
date: 2026-11-09
box-skill: none
---

Session profiles (`runtime.name = "session"`) now accept `runtime.options.release_delegation` instead of refusing it as an unknown key, so `crew-config.py resolve` and `crew-render.py` no longer exit 1 on an owner's recorded release delegation (#1435 parity). The session coordinator brief renders it in the same `Cut go:` line as the tmux coordinator brief, `none` when absent. The link check and the pack refusal apply as on tmux; tmux behaviour is unchanged.
