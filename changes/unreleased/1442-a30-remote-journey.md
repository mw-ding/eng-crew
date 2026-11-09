---
type: added
issue: 1442
pr: TBD
date: 2026-11-08
box-skill: none
---

The M20.1 lab now proves the A30 remote-builder journey for #209. In the `partition` scenario, the builder that `mdstack spawn` places on the lab host has its status lines pulled into the primary's mirror, and an `mdstack send --wait-ack` reaches its pane over the hardened SSH call and gets the ack back through the mirror. With `partition` and `exact-head` both run, the evidence record adds an A30 journey section: placement, status and ack, the disconnect and reconcile, the abandon, the local comparison and the physical limits of a simulated host. `crew-lab-docker.py teardown` adds its cleanup record to each run's evidence record.
