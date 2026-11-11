---
type: changed
issue: 978
pr: 1710
date: 2026-11-11
box-skill: none
---

Work-unit issues: an issue is a unit of work (a feature, fix or design), not a slice cut to a line budget, and each issue gets one PR split into logical commits that pass their tests where tests apply. The rule is in the coordinator planning duty in `docs/roles.md`, protocol stage 1, the coordinator dispatch skill and the builder's PR conventions. Reviewers read a multi-commit round commit by commit and judge the combined diff at head. Separate work, owner-decision or design-first items, gate-contract changes approved on their own and cross-area splits keep separate issues; M26 principle 9 (doc moves) stays. The portable spec's ~100-line slice sizing is now historical, not a budget. No gate changes.
