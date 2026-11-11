---
type: added
issue: 259
pr: TBD
date: 2026-11-10
box-skill: none
---

Spec bookends: every milestone opens with a spec slice and closes with a status-sync slice. The rule is in `docs/roles.md` and in a new shared fragment `templates/policy/coordinator/spec-bookends.md`, included in the tmux, session and Grok Bot coordinator briefs and listed in the dispatch skill. The status-sync slice sets Status cells, the README and runtime headers, settled questions and lessons, adds a row for each mid-milestone addition, and confirms every landed or superseded item is closed. A new `check-repo.py --only design-headers` check fails a doc whose H1 says "(design)" or "in design" unless that H1 or its banner names an open milestone of `docs/specs/portable.md` section 5. A closed milestone or an unknown reference fails, unless the doc is listed with a reason in `scripts/design-headers.txt`. `docs/deliverables.md` drops its stale "(design)" header. Merge gates are unchanged.
