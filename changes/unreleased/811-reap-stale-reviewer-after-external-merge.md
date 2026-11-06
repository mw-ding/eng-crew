---
type: fixed
issue: 811
pr: TBD
date: 2026-11-05
box-skill: none (tmux CLI only; no template changes)
---

A reviewer that stops with `done: #<n> stale` because its PR merged or closed is now reaped once, keeping its section files, whoever merged it, another runtime or GitHub account included. `crew route` returned early on every `stale` line, and the reviewer lead could not match it to a PR and head, so the run record kept its reviewer slot until a manual reclaim; a replay after the reap now retires.
