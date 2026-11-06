---
type: fixed
issue: 1156
pr: 1160
date: 2026-11-06
box-skill: none
---

`scripts/run-tests.py` now starts every test file without `TMUX` or `TMUX_PANE` and with its own fresh, private, short `TMUX_TMPDIR`, removed when the file finishes, so a bare `tmux kill-server` in a test can no longer reach the caller's tmux server (follow-up to the #818 server loss). A failing file's output is also written to a retained per-file log as soon as it finishes, named on its `FAIL` line (`--log-dir` picks the directory), so an interrupted suite no longer ends with bare `FAIL` lines and no output.
