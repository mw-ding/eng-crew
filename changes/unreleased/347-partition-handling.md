---
type: added
issue: 347
pr: TBD
date: 2026-11-08
box-skill: none
---

Runs on a role host now survive a partition. When `mdstack watch`'s pulls to a host fail 3 scans in a row, its runs are `unreachable`: their claims stay, nothing restarts or re-places them, `mdstack status` reads `unreachable since <time>`, and once the outage is older than `--stale` one `unreachable` escalate wake goes to the coordinator. The first pull that answers again queues a `reconcile` wake with each run's probe (the missed status lines come with the pull), plus a restart wake for each run found dead or missing. An owner's `mdstack kill <window> --discard --reason` on an unreachable run posts the reason, drops the primary's records and claim and writes `tombstones/<window>.json`; when the host returns, the watcher stops that run there and keeps its worktree if it holds unlanded work. The lab `partition` scenario now places a real run with `mdstack spawn` and proves all of this through a network disconnect.
