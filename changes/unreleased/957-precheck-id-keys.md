---
type: added
issue: 957
pr: 978
date: 2026-11-04
box-skill: none (scripts only; no rendered template change)
---

`crew-precheck.py` checks precheck `issue=` and selfgate `pr=` against the
resolved `ids.item` and `ids.change` patterns, all digits when none is
declared. `ids.marker_key = item` keys the selfgate record on `issue=`.
New optional `--item` and `--change` arguments carry the independently
known keys. A marker naming another item or change now blocks with
`marker for <value>, expected <id>`, and a selfgate read with neither
`--change` nor a record `number` blocks with `missing change key`.
`crew train`'s express gate passes the PR number and its one linked issue.
Slice B1 of #876; marker examples and operative wording follow in #958.
