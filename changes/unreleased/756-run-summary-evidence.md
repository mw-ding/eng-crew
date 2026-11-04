---
type: fixed
issue: 756
pr: TBD
date: 2026-11-04
box-skill: none (docs-only)
---

`docs/observe.md` no longer allows committing a run's `summary.md` to the PR
branch when a verdict relies on it, which contradicted the evidence placement
rule. Protocol §3 owns placement: evidence is inline in the PR body or signed
reviews, and the run summary reaches the PR only as promoted text. No gate
change.
