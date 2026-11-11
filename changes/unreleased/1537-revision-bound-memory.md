---
type: fixed
issue: 1537
pr: TBD
date: 2026-11-11
box-skill: none
---

Rendered briefs no longer inject core memory from a stale local checkout: each render reads `memory/owner.md` and the role files at the tip of the checkout's remote default branch (`repo.default_branch` on `origin`), resolved once and shared by every role output, and names that revision on stderr. A merged memory PR reaches the next `mdstack up` or `mdstack upgrade` without pulling the checkout, and local unmerged edits never enter a brief. A failed resolve, fetch or read fails the render closed; a root with no `origin` remote and no `memory/` adds nothing, as before.
