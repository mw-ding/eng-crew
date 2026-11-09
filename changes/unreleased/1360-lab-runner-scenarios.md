---
type: added
issue: 1360
pr: 1471
date: 2026-11-09
box-skill: none
---

The M20.1 local lab can now run `mdstack runner` scenarios over the real hardened SSH call to its Docker hosts with `environments/terminal/remote/lab/crew-lab-scenarios.py`. The client is the staged bundle, verified with the hosts' activated digest. A23's oracles (exact head against a local run, red results, idempotent request IDs, stale and unseeded heads, a scrubbed job env) run alongside failure injection. A network disconnect and a pause mid-job fall back locally, and the job's result is pulled afterwards. A runner-only restart recovers, and a recreated container never reports its lost job done. A partitioned role host is unreachable, so placement queues and the claim stays. Each injection is confirmed to break the SSH path.
