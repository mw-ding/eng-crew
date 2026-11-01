---
type: added
issue: 352
pr: 403
date: 2026-11-01
box-skill: deferred to #140
---

Metrics refresh adds flavor at the verdict head, escaped defects linked by whole-line issue-body references, and an engine-run proxy from commit trailers and attributed review/validation sections. Coordinator triage and the intake card gain the optional `Escaped from:` source line; unknown flavor and engine attribution stay blank. Offline tests cover the derivation and CSV/Markdown output. No merge gate changes.
