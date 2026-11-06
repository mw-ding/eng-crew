---
type: fixed
issue: 1078
pr: 1084
date: 2026-11-05
box-skill: none
---

`crew train check` now reports the evidence gate as `manual` when the only proof is a GitHub user-attachments image or video URL in `## Acceptance Evidence` or a head-bound builder fix review, the media form the protocol requires for web and mobile changes. Before, it reported `blocked` ("no evidence artifacts or reasoned N/A"), so a correct web-only or mobile-only PR never entered a train. Other media hosts, and URLs outside those posts, still block.
