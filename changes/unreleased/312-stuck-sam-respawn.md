---
type: changed
issue: 312
pr: TBD
date: 2026-11-01
box-skill: deferred to #140
---

The tmux coordinator brief now treats a window as `ambiguous` when `crew send` exits 4 (nudge not submitted) or an ack is still missing after the re-nudge, even if it probes `alive`, and still never restarts it, with one exception (#312, split from #308 ask 2; part of #110). The synthesizer window holds no worktree work, so the coordinator may kill and respawn it once per PR (`crew kill`, then `crew spawn synthesizer --pr <n>`), only while no land is in flight (`locks/merge.pid` absent), re-sends any other pending `land` because the kill drops its inbox, and asks the owner on a second miss. `docs/runtimes/tmux.md` names the exception in the Q7 failure policy. The brief-lint test gains a rule against restarting an `ambiguous` window outside this exception, and the rendered coordinator brief golden carries the new text.
