---
type: added
issue: 794
pr: 1119
date: 2026-11-06
box-skill: none (internal campaign fixture and doc; no template or box-skill changes)
---

The M25 campaign gains the A15 (direct land and negative merge gates) and A16 (stop-landing, grants and owner steer) scenario specs in `scripts/fixtures/campaign/` (25.12), at level a on sandbox tmux with the A14 fake forge. A lone ready PR behind main lands directly under `lone_pr_land = "direct"`, with no update-branch and no train PR, and two ready PRs land through a train. Each unsatisfied §7 gate blocks `crew train check`, and the land-time gates stop `crew train land` with nothing squashed. A head moved after the check is refused at the forge. A standing grant supplies only permission. A hold posted after approval stops the land. A project stop survives control-item close, restart and a moved head until its matching resume. Merge-ok counts only at the current head. The run filed #1118.
