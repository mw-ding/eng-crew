---
type: fixed
issue: 1559
pr: TBD
date: 2026-11-09
box-skill: none
---

`mdstack route` now keeps a merged PR's `pr-merged` wake queued for the coordinator, noted `milestone-complete`, when the merge closes the last open item of an active milestone or is a release cut (its `CHANGELOG.md` diff adds a version heading). The coordinator then closes the milestone and admits the next one at once instead of waiting for the owner. Other merged close-outs stay mechanical.
