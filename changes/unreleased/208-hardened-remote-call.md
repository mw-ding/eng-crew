---
type: added
issue: 208
pr: 733
date: 2026-11-03
box-skill: none (host script and multi-device doc only; no template changes)
---

`scripts/crew-remote.py` adds the hardened remote call for multi-device hosts. It has three parts. The entrypoint is the crew key's forced command: it takes one JSON request on stdin, never a shell string, and refuses unknown or not-built verbs, version skew, other SSH commands, paths outside its root and mutating verbs without a request id; a retried request id replays the first reply. The runner is a user-level service that keeps the host's crew tmux session alive, so runs outlive the SSH session, and writes a heartbeat. The primary's client `call()` takes only auth and host-key settings from the SSH config, then calls with `-F none`, batch mode, strict host keys, no forwarding or sent environment and bounded dead-peer timeouts, and returns `ok`, `refused`, `failed` or, on a transport failure only, `unreachable`. Only the `version` verb is built so far. The multi-device design gains a failure-semantics section.
