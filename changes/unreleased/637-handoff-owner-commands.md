---
type: added
issue: 637
pr: TBD
date: 2026-11-02
box-skill: pending coordinator mirror
---

Owner handoff chat commands: protocol §9 now defines `/crew handoff to <runtime-id> [drain | stop] [deadline <minutes>]`, `/crew handoff abort` and `/crew takeover from <runtime-id>`, given in the coordinator chat and recorded with `cmd-id=chat`. On tmux the new `crew handoff to|abort|takeover` re-reads the ownership record, refuses an illegal transition and posts the signed `draining`, `aborted` or `takeover` state on the control item. A drain writes `asks/handoff.json` so the watcher wakes the coordinator at the deadline, and the Stop guard now keeps its normal block while draining so the coordinator sees in-flight runs end. This is build issue A of the runtime handoff design.
