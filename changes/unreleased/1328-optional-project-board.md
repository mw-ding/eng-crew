---
type: fixed
issue: 1328
pr: TBD
date: 2026-11-07
box-skill: none
---

`mdstack doctor` no longer reports a missing crew board as `fail` when its identity cannot create one under the repo owner (a bot login on a user-owned repo, or a classic token without the `project` scope). It reports a `human` step naming the owner's `gh project create` and `gh project link` commands instead, so `mdstack bootstrap` proceeds. `doctor --fix` still creates and links the board when the identity can. The bootstrap, GitHub backend and GitHub tracking docs now say the board is recommended, not required.
