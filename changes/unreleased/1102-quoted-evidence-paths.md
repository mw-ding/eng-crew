---
type: fixed
issue: 1102
pr: TBD
date: 2026-11-06
box-skill: none
---

`crew train check` no longer treats an `evidence/` path quoted in a PR body or builder fix review as a required artifact. Fenced code blocks and code spans are quotes: a path inside them is ignored, such as `` `![R1](evidence/r1.png)` `` in a table cell, a rule name like `` `evidence/citation` `` or a path in a `sh`/`text` capture. The documented citation forms still count: a link or image, a code span holding just one artifact-shaped `evidence/` path (a subdirectory or a file extension, like `` `evidence/1/dir` `` or `` `evidence/run.log` ``), or a bare file path in prose. Found when #1080's body blocked its land.
