---
type: added
issue: 190
pr: TBD
date: 2026-11-01
box-skill: none
---

`crew doctor` checks whether a host can run the crew and prints one `ok`, `warn`, `fail` or `human` line per check with its fix hint: tools, `gh` logins, engines (the coordinator's, and a second one so the reviewer engine can differ), Codex hook trust and Claude Code folder trust for tmux, placeholder paths, the state dir layout, and the installed version against the latest release. It is read-only by default; `--fix` creates the missing state dir layout, and the steps only a person can take are listed at the end. Exit 1 on any `fail`.
