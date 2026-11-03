---
type: added
issue: 726
pr: TBD
date: 2026-11-03
box-skill: none (tmux CLI and profile schema only; no template changes)
---

`[hosts.<name>] forge = false` marks a forge-less host that takes runner jobs only. It needs no `engines`, and `validate` refuses it as the primary, with a non-empty `roles` or in `placement.hosts`, so placement never puts a role session there. `crew hosts` gains a `FORGE` column, and `crew host check` on a forge-less host shows the logins check as `n/a`, or `warn` when the runner finds a forge login there.
