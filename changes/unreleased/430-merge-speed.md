---
type: changed
issue: 430
pr: 439
date: 2026-11-01
box-skill: deferred to #140
---

Merge trains skip the duplicate local suite by default, with `--local` or a profile option to opt in and green train CI still required. A scoped, recorded owner mirror deferral can satisfy the tmux mirror gate for covered PRs that do not change live Grok Bot behaviour; merge records name its use and gate changes still require per-PR owner permission.
