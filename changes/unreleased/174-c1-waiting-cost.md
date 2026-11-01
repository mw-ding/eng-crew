---
type: changed
issue: 174
pr: 285
date: 2026-10-31
box-skill: none
---

Runtime contract C1 (`docs/runtimes/README.md`) says what waiting may
cost: waiting costs no model turns, only an actionable event or a due
backstop starts a turn, and a backstop's interval backs off while nothing
is in flight. Token-free pollers such as `crew poll` are not model-turn
polling; a runtime that cannot wait token-free may poll with model turns
only with backoff, declared as a C1 gap. Both binding tables re-checked:
Grok Bot declares its fixed hourly sweeper and no-op dispatcher wakes,
tmux its default watcher nudge (a possible second, empty turn per wake
for a Claude Code coordinator). Roadmap 15.1, decision #160 row 4.
