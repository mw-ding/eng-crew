---
type: added
issue: 566
pr: TBD
date: 2026-11-02
box-skill: pending coordinator mirror
---

Add runtime.options.max_active_milestones (integer at least 1, default 1) to both
runtimes. Coordinator briefs render the limit and prioritize the earliest
milestone, using later milestones only for spare builder capacity while
in-flight PRs in any milestone finish.
