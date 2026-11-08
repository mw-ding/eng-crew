---
type: added
issue: 1356
pr: 1407
date: 2026-11-08
box-skill: none
---

The M20.1 local lab now has a test-host image spec in `environments/terminal/remote/lab/`: a Dockerfile over an owner-approved, preloaded ARM64 Linux base pinned by digest that installs nothing from the internet, a key-only sshd config, and `crew-lab-host.py`. Its PID-1 `supervise` mode keeps sshd and the runner up and restarts either on exit, with the runner always under the non-root `crew` user in a scrubbed env, and its `ready` health check reads the runner heartbeat. `activate` verifies the bundle and SHA256SUMS copied in with `docker cp` before moving it into place and records the exact source SHA for a dev run; `authorize` writes the run's key as the only, forced and `restrict` authorized_keys line. No login, token, SSH agent or home is copied in. Proving it in a container needs the owner's Docker daemon.
