---
type: fixed
issue: 1322
pr: 1336
date: 2026-11-07
box-skill: none
---

`mdstack bootstrap` and `mdstack doctor` no longer report a `crew:*` namespace collision on a repo that uses the sensitive class. The crew label set now has thirteen labels: it adds `crew:sensitive` (the color and description already on the framework repo), `crew:express` and `crew:solo`, the other `crew:*` labels the protocol applies. An unknown `crew:*` label still fails as a collision. The GitHub tracking runbook and the GitHub backend label table list the full set.
