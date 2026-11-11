---
type: fixed
issue: 631
pr: 1657
date: 2026-11-10
box-skill: pending the coordinator's mirror of templates/runtimes/tmux/builder-lead.md
---

A worker whose engine is out of quota now moves to the next eligible engine instead of sitting idle. `mdstack spawn` filters the role's engine order before picking: a contributor-tier engine (Muse) is skipped on a private or unverified repository, so a Muse-first order starts the next engine rather than refusing (closes #1074); the launch policy still refuses a contributor-tier launch. The Claude Code, Codex and Cursor adapters declare `QUOTA`, their own usage-limit line. A run whose harness shows it probes `quota`, not `alive` or a trust dialog, and the watcher queues one `quota` wake for it. `mdstack restart` relaunches a quota run once on the next eligible engine in its role's order. It skips every engine the run exhausted, keeps unlanded work in place, records `exhausted` and the engine actually used, and refuses with no engine left. The builder-lead brief and the tmux liveness table name the new class.
