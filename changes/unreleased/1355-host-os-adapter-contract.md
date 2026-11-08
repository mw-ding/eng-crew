---
type: added
issue: 1355
pr: TBD
date: 2026-11-08
box-skill: none
---

The multi-device design now specs the host OS adapter contract for remote hosts: runner service install, start, stop, status and uninstall (a launchd agent on macOS, a systemd user unit with lingering on Linux, and a supervised fallback for containers without systemd), the process start-time read behind the liveness probe, read-only SSH listener and key-line checks, prerequisites and engine login presence. It also clarifies the acceptance criteria of the remote role issues (#345–#348), keeps the #209 dry run runner first, sets the attach TTY contract against today's `restrict` key and `-T` client, and states which criteria a local container or macOS VM can prove and which stay real-device in #716 (docs/runtimes/multi-device.md, Host OS adapters and Remote acceptance criteria and the local lab). Design only.
