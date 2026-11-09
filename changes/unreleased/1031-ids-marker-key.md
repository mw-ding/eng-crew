---
type: fixed
issue: 1031
pr: TBD
date: 2026-11-09
box-skill: none
---

A backend map's `[ids]` table now admits `marker_key`, the documented selfgate key choice that `crew-precheck.py` reads: `"change"` (key on `pr=`) or `"item"` (key on `issue=`). `crew-config.py` validates it in every map, refusing any other value by naming the allowed ones, carries it from the change backend's map into the resolved `ids`, and `resolve` prints `ids.marker_key` with `backend-map:<name>` provenance. Previously a map declaring it failed with `ids.marker_key: unknown key`. Maps without the key resolve as before.
