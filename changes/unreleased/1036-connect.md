---
type: added
issue: 1036
pr: TBD
date: 2026-11-10
box-skill: none
---

`mdstack connect <alias> [session]` opens the owner's own shell on an inventory host from any machine with the profile: with a session it runs `tmux new-session -A -s <session>` there (create or reattach), without one a plain login shell. The alias is the host name or `hosts.<name>.connect.alias`; the transport (`ssh`, `mosh` or `et`), proxy command and fixed options are profile data under `hosts.<name>.connect`, and arguments after `--` pass through to the transport. An unknown alias lists the known ones and exits 1. Docs: [Connect to a host](docs/runtimes/multi-device.md#connect-to-a-host).
