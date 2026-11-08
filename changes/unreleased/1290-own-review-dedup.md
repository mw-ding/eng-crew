---
type: fixed
issue: 1290
pr: TBD
date: 2026-11-08
box-skill: none
---

`mdstack route` no longer lets another runtime's posted review, validation or verdict markers suppress this runtime's reviewer pass. Its posted-marker dedup now counts only reviews authored by `identities.reviewer.gh_user` and signed with `identities.reviewer.name`, so a record from another login, or from another runtime sharing the login under a different signature, starts the local pass instead of leaving the PR without a verdict until a rereview steer. Live, queued and section-file dedup are unchanged.
