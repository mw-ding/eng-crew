---
type: fixed
issue: 591
pr: 599
date: 2026-11-02
box-skill: none (tmux only)
---

Stop `crew watch` crashing when a run record is reaped between listing and stat: the scan and `heartbeat()` now skip a record that disappears mid-scan. A watcher started while another live `crew watch` is armed exits 1 without touching its PID file or watch state, and a watcher removes `wake/watcher.pid` on exit only when the file holds its own PID.
