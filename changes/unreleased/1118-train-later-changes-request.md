---
type: fixed
issue: 1118
pr: 1154
date: 2026-11-06
box-skill: none
---

`crew train check` and `crew train land` now block a PR that has a later
changes request at head (protocol §7): a `steer cmd=rework` marker at head, or
a reviewer-identity `CHANGES_REQUESTED` review, posted after the passing
verdict. Before, both passed and land squashed the PR; only a changes verdict
marker at head was caught. A fresh verdict at head answers the request.
