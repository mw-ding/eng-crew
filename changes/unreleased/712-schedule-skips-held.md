---
type: fixed
issue: 712
pr: TBD
date: 2026-11-03
box-skill: none (scheduler and lead scripts and docs; no Grok Bot template change)
---

`crew schedule decide` no longer grants a pending handoff whose issue or PR is under a blocking `crew:hold`, or a PR that closes a held issue. The snapshot gains a `holds` input; held demand is left out of the ranking and the target's demand test, returned under `held` and shown as `held <n> <refs>` in `crew schedule summary`. An unreadable hold read holds nothing (`held unknown`), so one failed read never stops the crew; the leads' own hold checks stay the backstop. The handoff stays pending, so the item is ranked again once the hold lifts. `crew lead handoff` no longer reuses a prior message the lead already marked `done:`; re-sending the same kind and refs after a withdrawal starts a new handoff instead of reporting `acked`.
