---
type: added
issue: 621
pr: 0
date: 2026-11-03
box-skill: none
---

Gateway errors now reach the crew scheduler's input `schedule/errors.jsonl`. `crew watch` matches each live run's screen against its harness adapter's new transient-error text (Claude Code and Codex declare it; Pi, Cursor and Muse declare none) and appends each new line, and `crew train land` appends a stop or pause whose reason names HTTP 429, a 5xx or a rate limit. The same text from the same source within 10 minutes counts once. `crew schedule snapshot` already counts the file's last 10 minutes; nothing admits on it yet.
