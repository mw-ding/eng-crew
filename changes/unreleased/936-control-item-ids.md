---
type: added
issue: 936
pr: 972
date: 2026-11-05
box-skill: none (scripts and reference docs; no rendered template change)
---

`repo.control_item` may be a string id that fully matches the item pattern
the tracker backend's map declares in an optional `[ids]` table (F1 of the
tracker-native control item design). `crew-config.py resolve` loads `[ids]`
from the tracker and change backend maps, pack overlay first, and prints
`ids.item` and `ids.change` with `backend-map:<name>` provenance, defaulting
to today's GitHub number pattern. `validate` and `resolve` refuse a string
without a declared pattern, a non-matching or marker-unsafe string, a
boolean or a float, and a pattern that does not compile or matches an empty
or marker-unsafe id; a profile layer cannot set `[ids]`. An integer
`control_item` and GitHub rendering are unchanged; ownership and
`crew handoff` keep integer items until F2–F4.
