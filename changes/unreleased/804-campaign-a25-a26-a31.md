---
type: added
issue: 804
pr: TBD
date: 2026-11-06
box-skill: none (internal campaign fixtures and doc; no template or box-skill changes)
---

The M25 campaign gains three scenario specs in `scripts/fixtures/campaign/` (25.22), run on real sandbox tmux at level a. A25 covers owner presence, the ask SLA and notifications: an owner ask wakes the watcher once at its PT deadline, and an unreadable one at once. Present caps queue the next build. A recorded away entry gives full caps, still after its `until` passed, and its words lift no hold. A quiet entry keeps present caps, so busy builders drain without a kill. The Slack notifier, played by a loopback webhook, retries a refused delivery, never resends an uncertain one, dedupes a replay and never prints the webhook. After the owner's return it cancels pending messages and reports each outcome. A26 covers sleep and resume: nothing is queued while paused, the new head and red CI catch up once, a head handled before the pause is not replayed, three missed intervals start one overdue sweep, an empty queue starts no researcher, and a capped sweep takes its closed milestone only when its window starts. A31 covers metrics: a two-repo refresh counts rounds per PR and attributes lanes, a thin window cannot trip, a single-repo trip holds nothing, and a rollup trip holds only new feature work until the owner's waiver. An accepted intake card routes to the builder lead with its rigor unchanged.
