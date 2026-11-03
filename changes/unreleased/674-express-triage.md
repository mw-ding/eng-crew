---
type: added
issue: 674
pr: 689
date: 2026-11-03
box-skill: none
---

Add coordinator triage for the express lane. `item-flavor.py --labels` checks an `express` record's eligibility: a `crew:sensitive` or `crew:spec` item needs a whole-line `Owner override:` quote in the record, a `crew:solo` item never qualifies, and a missing `--labels` fails closed. An ineligible record resolves to the default with status `express-ineligible`, its `blockers`, and exit 1. `templates/triage-flavor.md` adds the express steps: sensitive classifier first, the check, then `crew:express` only on a recorded express flavor.
