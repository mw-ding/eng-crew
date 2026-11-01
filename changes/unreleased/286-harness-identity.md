---
type: fixed
issue: 286
pr: 309
date: 2026-10-31
box-skill: none
---

`crew spawn` and `crew restart` rejected Claude Code windows on a native
install (patch): the installer's `claude` is a symlink, and tmux reports
`#{pane_current_command}` as the target file's name, the version (for
example `2.1.314`), so the exact `claude` match failed each `claude-code`
launch there, reviewers and `trivial`-tier builders included. The start check
(`wait_harness`) now takes the evidence liveness takes: `claude` or
`codex` among the pane tty's foreground process names, or a pane command
equal to that name or to the name of the file it resolves to on `PATH`.
A version-shaped name alone still fails, and a dead pane still fails at
once. `scripts/test-crew-spawn.py` and `scripts/test-crew-restart.py` add
version-string pane tests; `docs/runtimes/tmux.md`, the expected
foreground process rows in `docs/runtimes/harness-adapters.md` and
`scripts/README.md` describe the check. Part of #110.
