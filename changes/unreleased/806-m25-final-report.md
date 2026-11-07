---
type: added
issue: 806
pr: 1186
date: 2026-11-07
box-skill: none (internal report and campaign fixtures; no template or box-skill changes)
---

`docs/metrics/m25-report.md` is the M25 final report (25.27). It reruns the 29 committed campaign scenarios at the final `main` SHA `a135a4d`, one fresh level-a sandbox each: 28 pass, and A04 fails on a stale fixture (#1174). It also runs the merged-head reruns the fix loop owed, the register rows carried to #806, the observed real-engine journeys, cost and usability, inventory-to-scenario traceability, and the limitations for the owner to accept before M25 closes. `scripts/fixtures/campaign/m25-final/` holds the per-scenario driver (`run.sh`) and the variant builder (`variants.py`) the report ran.
