---
type: added
issue: 751
pr: TBD
date: 2026-11-03
box-skill: deferred to #140
---

Add an intake-card issue template (M24 T5, `docs/triage.md`): `.github/ISSUE_TEMPLATE/intake-card.md` carries the `templates/intake-candidate.md` fields, and `config.yml` keeps blank issues allowed, so the card format is recommended, never required. The researcher's triage-sweep Card step now says when to extract: an empty queue `card` (rules could not parse the fields) gets one model-extracted comment in the card block shape, `unknown` for missing fields, and the `triage:card-extracted` label; nothing is gated on format. `docs/self-improve.md` points at the template; tests check that the template's fields match the card and parse.
