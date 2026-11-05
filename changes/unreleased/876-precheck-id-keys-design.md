---
type: added
issue: 876
pr: 969
date: 2026-11-04
box-skill: deferred to #140
---

Design note (proposed, not in effect) for precheck and selfgate markers
keyed on a backend's declared item or change id. Protocol §2 gains a
proposal section: `crew-precheck.py` checks `issue=` against the tracker
map's `ids.item` and `pr=` against the change map's `ids.change` from the
ID declaration of #875, digits when undeclared; an optional
`marker_key = "item"` in the change map keys the selfgate record on
`issue=` instead of `pr=`; each mode has an exact field set; and the key is
compared with an independently supplied `--item` or `--change` id, never
the marker's own value. §4, `profile.md` and `packs.md` point to it. No
gate, key or behaviour changes until build slices #957 and #958 land.
