---
type: fixed
issue: 287
pr: 300
date: 2026-10-31
box-skill: deferred to #140
---

tmux watcher owner-ask deadline (restores documented behaviour): the C8
row and Q1 in `docs/runtimes/tmux.md` said the watcher wakes the
coordinator at an owner ask's §6 auto-apply time, but `crew watch` had no
such timer, and its backstop backs off to 16 × `--backstop` while no run
is recorded, so a deadline could pass hours before the coordinator woke.
The coordinator brief now writes each open ask's deadline to
`<state-dir>/<owner>__<repo>/asks/<n>.json` (`{"deadline": ...}`, ISO
8601 with its UTC offset) and deletes it when the ask closes. `crew watch`
queues one `ask: <n> deadline <time>` wake per deadline on the first scan
at or after it, cuts its scan sleep short so that scan lands on the
deadline, whatever the backstop, and wakes at once on an unreadable
deadline. The C8 row, Q1 and the `crew watch` source list in
`docs/runtimes/tmux.md` name the `ask:` wake. Tests in
`scripts/test-crew-watch.py` use an injected clock; golden
`scripts/fixtures/render/tmux/runtime/coordinator.md` updated; Grok Bot
renders unchanged. Refs #110.
