---
type: fixed
issue: 1502
pr: 1624
date: 2026-11-10
box-skill: none
---

The builder lead's 60-second admission backstop no longer re-types an acknowledged, deferred handoff into the lead window on every poll. `mdstack lead report builder REASON REF... --id ID` records the handoff's inbox id on its `deferred:` status line; the backstop then re-runs the scheduler walk, persisting only the target's progression so a throttled target recovers, and nudges only when that ref is admissible. Slot releases and the coordinator backstop still nudge it, an unacknowledged or unreported id keeps the normal retry, and the handoff stays pending demand until a worker record exists.
