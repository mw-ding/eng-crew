---
type: added
issue: 1357
pr: TBD
date: 2026-11-08
box-skill: none
---

The M20.1 local lab can now set up and tear down its Docker role hosts with `environments/terminal/remote/lab/crew-lab-docker.py`. `setup` extends the campaign run manifest with the pinned Docker context and endpoint, the image ID, the bundle hashes and every container, network and volume ID. It refuses before any Docker mutation on a name or run-label collision. Hosts get no mounts, SSH is published on `127.0.0.1` only, and a per-run SSH config maps lowercase aliases to loopback ports. Every child runs with an isolated HOME and without inherited `CREW_*`, forge tokens, SSH agents or `TMUX`. `--n3` puts each host on its own internal network with a driver, and `n3` reports N3 unproved unless every lateral probe is denied. `teardown` saves evidence, then removes only manifest-owned IDs whose owner label still matches, and checks the state sentinel and a tmux decoy.
