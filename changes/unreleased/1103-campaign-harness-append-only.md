---
type: changed
issue: 1103
pr: 1104
date: 2026-11-06
box-skill: none
---

`docs/campaign-harness.md` is restructured for append-only edits, with no content change: the committed-spec list and the fresh-sandbox list carry one scenario per line in ID order, and each scenario's notes (A06 and A07, A08 to A10, A11 and A32, A12, A20, A21, A22, A28) sit under their own heading in ID order, after the shared runner, environment, decoy and results text. A new campaign then adds lines without touching its neighbours, so merge-ups of M25 campaign PRs stop re-resolving the same line.
