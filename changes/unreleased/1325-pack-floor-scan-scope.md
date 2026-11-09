---
type: fixed
issue: 1325
pr: TBD
date: 2026-11-09
box-skill: none
---

`crew-pack.py check` no longer refuses a pack that selects its CI backend in its own layer. The floor scan matched a floor-control key name (`ci`, `hold`, `record` and the rest) at any depth, so `[backends.ci] name = "<connector>"` in a pack's `profile.toml` or environment defaults failed as floor F1 and every project had to repeat the selection. The scan now looks only where floor controls live: the `[flavor]` table with its custom flavors and classes, and `runtime.options`. A real loosening such as a custom flavor's `ci_waiver = true`, `hold_label_blocks = false`, a looser flavor or a merge grant is still refused.
