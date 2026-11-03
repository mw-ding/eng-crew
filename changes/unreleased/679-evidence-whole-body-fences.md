---
type: fixed
issue: 679
pr: 684
date: 2026-11-03
box-skill: none
---

`crew train check` now accepts an inline `sh` + `text` reproduction anywhere in the PR body, such as captures under `## Test Output` that the Acceptance Evidence table references, as well as in signed builder fix or ci-fix reviews at head. Required `evidence/` artifact paths are still read only from the Acceptance Evidence section and those builder reviews, and reviewer or coordinator posts still count for neither.
