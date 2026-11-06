---
type: fixed
issue: 1079
pr: TBD
date: 2026-11-05
box-skill: none
---

`crew train check` no longer blocks the evidence gate for good when a PR body cites an `evidence/` path that is not in the head tree. A builder `pass=fix` or `pass=ci-fix` review at head that carries an inline `sh`/`text` reproduction now supersedes the stale body paths: the gate reports `manual` ("missing artifacts superseded by inline fix proof at head: ...; verify the proof and validation") instead of `blocked`. The body is never edited and `evidence/` cannot be committed, so the block used to leave the PR no way out, although verification Q5 counts the inline proof and treats a path as no evidence. With no inline proof in a head-bound fix review, or proof only in the body, a missing path still blocks. Found by the M25 A12 run on #791.
