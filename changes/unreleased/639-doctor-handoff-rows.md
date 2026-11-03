---
type: added
issue: 639
pr: 714
date: 2026-11-03
box-skill: none (tmux CLI only; no template changes)
---

`crew doctor` adds the runtime handoff rows (build issue C in `docs/handoff.md`): `control item` (ok when `repo.control_item` is set and its ownership record reads; `warn` when unset, which keeps legacy operation; `fail` when unreadable, since every wake is then read-only), `runtime instance` (`warn` when `runtime.instance` is unset) and `owning runtime` (ok when this instance owns the repo; `warn` when another instance owns it, a handoff is draining or in transit, or no `claimed` marker exists yet). The bootstrap preflight table gains the matching row 22.
