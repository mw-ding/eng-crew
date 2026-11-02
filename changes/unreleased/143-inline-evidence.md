---
type: changed
issue: 143
pr: 448
date: 2026-11-01
box-skill: coordinator mirror required
---

Make runtime evidence inline only in the change body and signed reviews, with
copyable text recipes, GitHub media attachments and explicit size limits.
Update the evidence merge gate, adapters and role templates; remove committed
evidence from this tree and reject a root `evidence/` directory. No history
rewrite; existing product evidence cleanup remains a separate change per repo.
Keep the incoming builder pre-review checklist consistent with inline proof,
and remove evidence files added on main before this change lands.
