---
type: added
issue: 1351
pr: TBD
date: 2026-11-10
box-skill: none
---

The session runtime now has an async land binding: `resolve` accepts `land.mode = "async"` with its change placeholder and `[land.status]` map under `runtime.name = "session"`, `mdstack land request|resume|done` run on a session profile, and the rendered session synthesizer brief's step 3 lands through `mdstack land request`, which polls the declared status map within `land_timeout` and refuses on `failed`, a stale head or an unknown status. Sync session renders and every tmux render are unchanged.
