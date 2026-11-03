---
type: added
issue: 212
pr: 718
date: 2026-11-03
box-skill: pending coordinator mirror
---

Runtime handoff resume and prompt stop (roadmap 21.4). On tmux, `crew handoff reconcile` now prints the whole reconcile table: `adopt`, `hold` (a head or stage tag moved), `skip`, `gone`, `rerun` for kept runs and for pass markers posted in transit, `missed` items and `rule` differences. `crew handoff ack` posts `acked` with that plan once per handoff id, refusing while a rule difference has no owner answer; a takeover's ack carries the manifest. `crew handoff lift` removes `crew:hold` only from the manifest's `holds_added`, once `stopped` is posted, the owner confirms or the outgoing release reads the record. On the outgoing side, `crew poll` queues one `ownership: lost` wake after the ack, `crew watch` refuses to re-arm, and `crew handoff stopped` does the teardown from a process detached from the crew session: it disarms the watcher, runs `crew down` keeping every worktree, and posts `stopped` with the kept worktree names once the watcher and session are gone. The resume steps now apply a diverged set's hold after the ack and before dispatch, and the Grok Bot wiring template gains the stop and return checklist.
