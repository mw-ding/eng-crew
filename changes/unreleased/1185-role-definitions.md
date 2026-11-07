---
type: changed
issue: 1185
pr: 1255
date: 2026-11-07
box-skill: none
---

Each role is now one definition file, `roles/eng/<role>.toml`, replacing `roles/eng.toml`. Besides its existing keys it carries its identity defaults, whether a profile may leave the identity out, an optional cap with its default and minimum, its default tier, how a run completes (`completion`) and who relays its result (`relay`), the passes host placement may route, and the rendered brief bootstrap's self-test requires (`discovery`). The profile's core identity defaults, optional identities, tmux role caps, placement passes, the renderer's optional roles, `crew spawn`'s default tier, run completion, `crew route`'s coordinator relay and bootstrap's self-test derive from those files, so an auxiliary role that reuses an existing lifecycle is one definition, its brief and tests. `crew-roles.py` now validates the directory. Review, validation and land stay explicit core contracts; existing roles render, resolve and behave as before, and no gate or marker rule changes.
