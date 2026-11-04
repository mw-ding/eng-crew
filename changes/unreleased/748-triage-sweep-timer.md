---
type: added
issue: 748
pr: PRNUM
date: 2026-11-04
box-skill: none
---

Add the always-on triage switch and sweep timer (M24 T2, `docs/triage.md`): an optional `[triage]` profile table (`enabled` default false, `interval_hours` default 6, `repos` default the project's repo, `rules`, `mode` `shadow` | `apply` default `shadow`) with validator rules; the tmux `researchers` cap now defaults to 2; `crew spawn researcher --sweep` starts a `riley-sweep` window with no item; and `crew watch` starts that sweep, with no model turn and no wake, once `interval_hours` passed since the last slot in `triage/sweep.json` or at once when overdue on wake, skipping the slot when `triage/queue.json` lists no items.
