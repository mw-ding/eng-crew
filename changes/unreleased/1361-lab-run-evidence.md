---
type: added
issue: 1361
pr: TBD
date: 2026-11-09
box-skill: none
---

Each M20.1 lab scenario run now writes an evidence record under `state/lab/runs/`, as JSON plus a Markdown copy to paste into a PR. The new `environments/terminal/remote/lab/crew-lab-evidence.py` writes it. The record covers the hosts, the image digest, the bundle and source hashes, the transport, every injected event and a timeline. The whole record is marked simulated and not a real device, and each Docker network control is labelled simulated. The sample checks and the partition's claim are labelled stubs. A scenario that did not run is `skipped` with `evidence: false`.
