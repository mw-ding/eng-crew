---
type: fixed
issue: 1366
pr: 1400
date: 2026-11-08
box-skill: none
---

The watcher's gateway-error match now counts only a harness's own error line: Claude Code's `⎿  API Error <429|5xx>` line at the result gutter and Codex's `■` error banner. Tool output, file names, diffs and quoted issue bodies that name `rate-limit`, `429` or `API Error` no longer land in `schedule/errors.jsonl`, so they cannot push the scheduler's error signal high and cut its target. `docs/runtimes/harness-adapters.md` describes the anchored lines.
