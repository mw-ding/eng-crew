---
type: changed
issue: 1569
pr: 1596
date: 2026-11-10
box-skill: none
---

The tmux synthesizer is now a long-lived lead. `mdstack up` starts it in window 1 next to the builder and reviewer leads, and the watcher supervises and restarts it the same way. `mdstack route` hands `review-approved`, `selfgate-passed`, `ci-passed` with an approval or self-gate pass at head, and approved `merge-up` events straight to its durable inbox, which is its land queue. Every §7 gate is still checked live before each land. Route still does merged-PR close-out and now also queues the away-only Slack land message and hands ready `Depends on` dependents to the builder lead, and the coordinator is woken only for exceptions: owner merge-ok, `crew:sensitive`, holds, `main red` and lead faults. With the lead installed, `mdstack spawn synthesizer` refuses, and the coordinator recovers a land with `mdstack lead handoff synthesizer land`.
