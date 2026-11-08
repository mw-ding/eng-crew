---
type: fixed
issue: 1290
pr: 1373
date: 2026-11-08
box-skill: none
---

`mdstack route` no longer lets another runtime's posted review, validation or verdict markers suppress this runtime's reviewer pass. Its posted-marker dedup now counts only reviews authored by `identities.reviewer.gh_user` and signed with `identities.reviewer.name`, so a record from another login, or from another runtime sharing the login under a different signature, starts the local pass instead of leaving the PR without a verdict until a rereview steer. The head-verdict check that gates a new-head or post-build reviewer spawn, and the approval check that lets a pure merge-up skip review, apply the same rule, so another runtime's `pass=verdict` no longer consumes the wake; builder fix notes and coordinator rereview steers still count. Live, queued and section-file dedup are unchanged.
