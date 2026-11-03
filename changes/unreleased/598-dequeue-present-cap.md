---
type: fixed
issue: 598
pr: TBD
date: 2026-11-02
box-skill: none
---

`crew dequeue` now decides idle-builder reclaim against the same effective builder pool cap as admission (the owner-present cap, or the recorded-away cap), not the full `builders` cap, so a full builder band with the present cap reached no longer reclaims an idle builder whose slot it cannot use.
