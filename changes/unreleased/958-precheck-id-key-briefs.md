---
type: changed
issue: 958
pr: TBD
date: 2026-11-04
box-skill: deferred to #140
---

The precheck and selfgate id keys from #876 are now operative protocol
wording: the precheck marker's `issue=` is the tracker item id and the
selfgate record keys on `pr=`, or on `issue=` when the change backend declares
`marker_key = item`, all digits until a backend map declares `[ids]`. The
express lane, the tmux builder, reviewer and synthesizer briefs and the Grok
Bot reviewer and synthesizer briefs pass `crew-precheck.py --item` with the
issue the PR closes, and treat a marker for another item as blocking. Slice B2
of #876.
