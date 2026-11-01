---
type: added
issue: 158
pr: 306
date: 2026-10-31
box-skill: none
---

Multi-device design: `docs/runtimes/multi-device.md` designs role runs on
several hosts of a private overlay network under one primary host, as a
capability of the tmux runtime (not a new binding), carrying out the #160
row 6 decision. It covers overlay assumptions, a host inventory profile
extension (`[hosts.<name>]` with capabilities, `max_runs`, roles;
`[placement]` affinity and capability rules; proposal for #204), the
`place()` function in `crew spawn` with a recorded `--host --reason`
override, `crew host check` / `prepare` and `crew hosts`, the hardened
remote call and per-account runner, C1–C8 across hosts with gap lines,
failure and partition handling (the `unreachable` class is never
restarted or re-placed), the security model, alternatives per decision,
and a map onto build issues #204–#209 plus proposed 20.8–20.12. Docs
only; no rule, gate, cap, marker field or label changes. Roadmap 20.1.
