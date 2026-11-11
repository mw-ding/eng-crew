---
type: fixed
issue: 1633
pr: 1655
date: 2026-11-11
box-skill: none
---

A builder left idle at its prompt after a Claude Code API error now reaches its lead. The Claude Code adapter's transient-error text also matches `⎿  API Error: Connection lost mid-response` and the gateway's `429 … capacity … exhausted` line, still at the harness's own indent only, so each counts once per error window in `schedule/errors.jsonl`. `mdstack watch` wakes the builder lead with a `stale` wake of liveness `claim` when an alive builder holding acknowledged unfinished work (an `ack:` with no later `done:`, `blocked:` or `failed:`) has a claim heartbeat older than 15 minutes, even while the supervisor heartbeat keeps its status file fresh. It fires once per claim silence and never for a mid-turn harness, a held item or a builder waiting after `done:`. Existing liveness, identity and one-restart rules are unchanged.
