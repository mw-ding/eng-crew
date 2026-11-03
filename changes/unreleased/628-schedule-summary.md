---
type: added
issue: 628
pr: 706
date: 2026-11-03
box-skill: none (tmux only)
---

`crew schedule summary` prints one line from the latest scheduler decision: busy workers against each pool's cap, the target, the machine signals, queued demand by kind, deferrals by reason and orphaned runs with their process ids. `crew watch` prints that line after every exit line, and finishing work (classes 1–6) deferred for `stuck_after` seconds (new profile option, default 1800) sends one `schedule-stuck` wake with the item, its reasons and the latest snapshot. Deferrals themselves never wake the coordinator.
