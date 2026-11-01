---
type: security
issue: 184
pr: 413
date: 2026-11-01
box-skill: deferred to #140
---

**Breaking:** Sensitive path classification now requires per-change owner merge-ok; no standing grant covers `crew:sensitive`. Profiles can extend mandatory path defaults. Migrate by classifying changes at triage/open/push and recording owner overrides; synthesizers and merge trains enforce the label.
