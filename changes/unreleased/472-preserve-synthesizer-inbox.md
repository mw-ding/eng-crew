---
type: fixed
issue: 472
pr: 500
date: 2026-11-01
box-skill: none
---

Keep the synthesizer window alive after a completion while another land request
or undelivered inbox message remains. Serialize inbox appends with the route's
check and reap so a pending request cannot disappear during cleanup.
