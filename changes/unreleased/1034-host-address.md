---
type: added
issue: 1034
pr: 1589
date: 2026-11-10
box-skill: none
---

An inventory host can now carry its reachable DNS name: optional `[hosts.<name>] address` (a dotted DNS name such as `host-a.region.example.com`; no IP literal, `user@` or `:port`) beside the short label, which stays the stable key for placement, run records and `mdstack host check <name>`. `mdstack host check` and `host prepare`, role runs on the host (spawn, probe, kill, pull, send, attach) and `mdstack runner` jobs all connect to the address; a host without one still connects to its label, so existing profiles are unchanged. `core/crew-config.py validate` refuses an address that is not a dotted DNS name.
