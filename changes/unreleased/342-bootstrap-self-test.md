---
type: added
issue: 342
pr: TBD
date: 2026-11-01
box-skill: none
---

Bootstrap now validates and re-renders every role after installation, checks deployed content and target hashes, reruns doctor, and records failed checks. Explicit `--smoke` queues one docs-only pipeline test issue per install after checks pass; dry-run creates no issue.
