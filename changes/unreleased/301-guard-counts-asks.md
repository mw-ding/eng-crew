---
type: fixed
issue: 301
pr: 355
date: 2026-11-01
box-skill: none
---

tmux turn-end guard counts open owner asks (restores documented
behaviour): Q1 step 4 in `docs/runtimes/tmux.md` said `crew guard` blocks
the coordinator's stop while an owner ask is open and no watcher is armed,
but the guard counted only run records and a non-empty
`wake/queue.jsonl`, so the coordinator could end its turn with an ask open
and nothing armed to wake it at the deadline. Since #287 gave each open
ask a record, `asks/<n>.json`, the guard now counts any record there as
work in flight, an unreadable one included. The `crew guard` section of
`docs/runtimes/tmux.md` and the guard's docstring say so; the Q1 step 2
reason list and the `crew watch` usage already named the `ask:` wake.
Test in `scripts/test-crew-guard.py`. Grok Bot runtime unchanged. Refs
#110.
