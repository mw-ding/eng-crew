---
type: fixed
issue: 1176
pr: TBD
date: 2026-11-07
box-skill: none
---

`crew lead ensure` now creates the state root's `status/` directory before it starts a pool lead, so a fresh lead on a new install can append its first `ack:` to `$CREW_STATUS` and `crew send ... --wait-ack` sees it instead of timing out with `no ack`. Existing state roots already had the directory and are unaffected.
