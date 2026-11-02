---
type: changed
issue: 166
pr: 557
date: 2026-11-02
box-skill: none
---

CI feeds the repository CREW_DENYLIST secret to the repo guard through a private temporary file, without logging its terms, and removes the file on success or failure.
