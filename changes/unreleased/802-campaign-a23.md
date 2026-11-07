---
type: added
issue: 802
pr: 1107
date: 2026-11-06
box-skill: none (internal campaign fixtures, test and doc; no template or box-skill changes)
---

The M25 campaign gains the A23 (forge-less runner) scenario spec in `scripts/fixtures/campaign/` (25.20), with a fake SSH transport, sample checks and step helpers in `a23/`. It runs at level a: `crew runner` loops back over the fake transport to the real host entrypoint. An exact-head job stores its result, prints its runner reference and keeps its logs on the host, and the runner capture names host, job and head. The host sees only `seed`, `job` and `result`, its job env is scrubbed, and it makes no forge, engine or role call. A duplicate job id or request id returns the first job. A red remote test is a red run. Unreachable, refused and failed transport run the same commands locally and name the reason, and a late result is discarded. A stale head, a capture at another head and an unseeded head are refused.
