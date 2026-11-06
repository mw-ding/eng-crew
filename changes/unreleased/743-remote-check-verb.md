---
type: fixed
issue: 743
pr: 1117
date: 2026-11-06
box-skill: none
---

`crew host check` can now report a remote host `ready` against the real entrypoint. `crew-remote.py` builds the `check` verb: it returns the `tools`, `project mirror`, `logins`, `runner` and `capacity` rows, the prepared `projects` and the `load` (jobs still running). `inspect_host` now sends the request through the hardened, versioned `call()`. Before, the entrypoint refused every check, first for version skew and then as `verb check not built`, so `crew host prepare` on a forge-less host exited 1 after a good seed and `crew runner run` without `--host` never picked a host. A new test runs `crew host prepare` and `crew host check` through a loopback `ssh` that execs `crew-remote.py` and shows the forge-less host `ready`. `--fix` still repairs nothing on a remote host; each failing row's hint names the step.
