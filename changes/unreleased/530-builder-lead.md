---
type: added
issue: 530
pr: 534
date: 2026-11-01
box-skill: deferred to #140
---

Long-lived builder lead with a reserved session window, durable reference handoffs, cap/load/suite admission decisions, and one identity-checked restart with its inbox and workers preserved. The coordinator hands builder lifecycle to the lead; automatic cross-pool dequeue stops for lead-owned builders. Fixtures cover scaling, replay, restart, ambiguity, and cleanup boundaries. Part of the role-lead split under issue #521.
