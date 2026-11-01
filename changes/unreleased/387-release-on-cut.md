---
type: added
issue: 387
pr: 419
date: 2026-11-01
box-skill: none
---

Publish releases when a CHANGELOG cut PR lands on main, after validating the real cut and verifying the owner's merge-ok at the merged PR head and release actor. Non-cut pushes skip cleanly; dispatch remains for dry runs and approved fallback publishing. Releases attach the bundle and checksums, then notify and close the linked release issue.
