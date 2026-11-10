---
type: added
issue: 1520
pr: 1547
date: 2026-11-09
box-skill: none
---

`mdstack spawn researcher --reflection WINDOW [--log N] [--input-sha SHA] [--run-id ID]` starts a reflection run, riley-reflection, in a fresh worktree at the input SHA, under the existing researcher cap. Its run ID, reflection log issue, input SHA and window are fixed at the request and carried intact through the cap queue, `mdstack dequeue` and `mdstack restart`. Restart first rechecks the log for a posted report covering the window and refuses when one is there. A `done: reflection <window> <url>` completion puts the report URL on the wake relayed to the coordinator, and reaps only the run for that window. Combining it with `--issue`, `--pr`, `--sweep`, `--docs-pass` or `--train` is refused.
