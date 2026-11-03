---
type: added
issue: 675
pr: 697
date: 2026-11-03
box-skill: none
---

`scripts/metrics-refresh.py` adds the express-lane metric columns to `prs.csv` and `prs.md`: `lane`, `selfgate_mode`, `selfgate_reviews`, `selfgate_findings`, `dispatch_to_merge_min`, `ci_red_rounds` (every lane), `merge_ups` and `reverted`. The metrics README defines each field. Offline tests cover every column through a fake `gh`.
