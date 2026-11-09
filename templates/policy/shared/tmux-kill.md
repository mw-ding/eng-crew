Destructive tmux calls take the sandbox `-S` socket with `TMUX`/`TMUX_PANE`
unset, or `campaign-sandbox.py teardown`; `TMUX_TMPDIR` alone isolates
nothing. Run tests via `scripts/run-tests.py`, not `python3 test-*.py`.
