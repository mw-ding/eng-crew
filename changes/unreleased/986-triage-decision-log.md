---
type: fixed
issue: 986
pr: 1022
date: 2026-11-05
box-skill: none (docs-only)
---

`docs/triage.md` no longer hard-codes a decision-log issue number. The triage sweep reads owner decisions from the project's decision-log issue, the tracking issue that `away-control.json` names (protocol §6 Owner away mode), and from the item. #110, the issue it first named, was closed on 2026-11-05, and the decision log moved to #985. Links to past #110 comments stay as history.
