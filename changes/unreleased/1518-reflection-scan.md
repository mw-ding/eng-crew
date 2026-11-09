---
type: added
issue: 1518
pr: 1526
date: 2026-11-09
box-skill: none
---

`scripts/reflection-scan.py` builds a deterministic JSON evidence index for a reflection window (M39 R2). Offline, it reads forge snapshots, the lessons and findings buffer at a named SHA, owner decisions and sanitized runtime observations. It selects every issue or PR opened, closed or corrected in the window whatever its placement, and keeps older linked lessons as context. One incident per card and fix chain, and one per class and site however many cards report it, keyed by `triage-clusters.py`'s own keys; triage stays open-only. Evidence stays `reported`, `confirmed` or `superseded`, and a missing input is listed and null, never zero.
