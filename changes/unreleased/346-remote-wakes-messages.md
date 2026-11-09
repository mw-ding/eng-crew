---
type: added
issue: 346
pr: TBD
date: 2026-11-08
box-skill: none
---

Runs on a role host now wake the coordinator and take messages. Every `runtime.options.host_scan_interval` (default 15 s) `mdstack watch` makes one `pull` per role host with runs and copies new status lines into the primary's `status/<window>.status` mirror, which wakes as a local status file does. The mirror's own size is the offset and a prefix digest guards it, so an interrupted or repeated pull and a primary restart lose and double no line. `mdstack send` delivers through the host's new `send` verb (inbox line and verified nudge there; exit 1 when the host is unreachable, never queued), and `mdstack acked` and `send --wait-ack` pull before reading the ack. The lab gains a `status-pull` scenario that proves the pull through a network disconnect.
