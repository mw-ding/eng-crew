---
type: added
issue: 1232
pr: 1280
date: 2026-11-07
box-skill: none
---

`crew action`, the terminal binding of the actions CLI contract: it keeps the contract's JSON envelope, exit codes and `--capabilities`, and implements `check-ownership`, `heartbeat`, `notify`, `ack` and `report` over the same control item, claim, inbox and status files the tmux and herdr runtimes read today. Every other action answers `unsupported` (exit 6). The builder, reviewer and synthesizer policy fragments now call `crew action heartbeat` and `crew action report` instead of editing the claim or status file by hand; the status lines they write are unchanged.
