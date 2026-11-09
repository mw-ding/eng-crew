---
type: added
issue: 207
pr: 1457
date: 2026-11-08
box-skill: none
---

With a `[hosts]` inventory, `mdstack spawn` places each role run with a pure decision function (multi-device placement): project affinity, capability rules by role, pass and changed path, the tier's engine order before load, then the least-loaded ready, reachable host below `max_runs`. With no eligible host it queues the request with one reason per host; with no engine it refuses. `--host <h> --reason "<why>"` overrides the host and posts the reason on the item first, and a failed post spawns nothing. The run record keeps `host`, `placement` and the rejections, and `mdstack status` gains a HOST column. A placement on a host other than the primary refuses until remote run lifecycle (#345) lands.
