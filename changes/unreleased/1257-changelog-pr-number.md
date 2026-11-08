---
type: added
issue: 1257
pr: TBD
date: 2026-11-08
box-skill: none
---

`scripts/check-changelog-pr.py` gains `--pr N`, and CI passes the PR's number on `pull_request` events: a fragment the PR adds or changes whose `pr:` is `TBD` or another PR's number now fails the changelog check, naming the fragment, so a fragment can no longer merge with `pr: TBD` and surface only at the next cut. A merge-train PR (`crew/train-*`) carries its members' fragments and is refused only for `pr: TBD`. Push events and release cuts behave as before. `CONTRIBUTING.md` says to fill in the number before review.
