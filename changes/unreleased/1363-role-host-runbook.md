---
type: added
issue: 1363
pr: 1429
date: 2026-11-08
box-skill: none
---

A role-host runbook in the multi-device design: how the owner adds and removes a host that takes builder and reviewer runs, as the runner-host runbook's differences (toolchain, logins on the host itself, profile, prepare) plus per-OS runner service steps for a macOS launchd agent, a Linux systemd user unit with lingering, and the lab-only supervised container. A proof-limits table states what the local lab's Linux containers and macOS VM can show and what still needs the real second device (#716) and a real overlay (N1 to N4). Docs only; placement and remote role runs (#207, #345 to #348) are still not built.
