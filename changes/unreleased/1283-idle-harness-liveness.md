---
type: fixed
issue: 1283
pr: 1396
date: 2026-11-08
box-skill: none
---

`mdstack watch` now reports a working run as stalled when its tmux pane has printed nothing for `--idle-stall` seconds (default 1800, 30 min; `0` turns it off), even while its claim, heartbeat or status file keeps being refreshed: the wake is `stale` with liveness `idle` and action `escalate`, once per silence, and the reviewer pool escalates it rather than treating a re-probed `alive` worker as plain silence. A builder after `done:`, a finished run and a lead or synthesizer with no work are not flagged, and the herdr backend, which reports no pane activity, is not checked. The builder and reviewer briefs now forbid background loops that refresh the claim, heartbeat or status file; a long wait uses the harness's own background-task notification. Before this, a builder's self-refreshing claim loop hid it idle at its prompt for about 2h50m.
