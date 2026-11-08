---
type: fixed
issue: 846
pr: TBD
date: 2026-11-08
box-skill: none
---

`mdstack route`'s merged-PR close-out now checks each issue in the PR's `closingIssuesReferences` and, if GitHub's auto-close missed it (seen on train lands), closes it with a close-out note, so dependents no longer read a landed issue as unfinished. An issue that was reopened stays open, so an issue that must stay open until a later release keeps that state.
