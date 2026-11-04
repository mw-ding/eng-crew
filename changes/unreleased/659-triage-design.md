---
type: added
issue: 659
pr: TBD
date: 2026-11-04
box-skill: none
---

Add `docs/triage.md`, the always-on triage design (M24): a fresh researcher session sweeps new and changed issues and intake cards every `interval_hours` (default 6) on the watcher's timer, after a zero-model scan in `crew poll` that also starts an immediate sweep for a P0 candidate. Each decision looks up duplicates, lessons, findings and recorded owner decisions first and cites them; rules decide before the model, and ambiguity fails closed to a proposal. Low-risk, reversible changes may auto-apply, closes and active-milestone moves are only proposed, and gates, flavors, merge permission and owner config are never touched. Proposals live on the items with a daily log issue and nothing is sent to the owner; sweeps start in shadow mode until 8 of 10 owner spot checks pass. It supersedes #427, folds in #374 and #299 and lists build issues #747–#751. Design only: it adds no rule until those land.
