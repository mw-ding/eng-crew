# Session loss, 2026-11-09

## A worker pane's bare tmux kill reached the crew server

- **Date:** 2026-11-09
- **Source / evidence:** the researcher's finding on #1474; fix #1475,
  merged in #1482.
- **Finding:** A worker's test cleanup ended the crew server.
- **Impact:** Every window died; the owner restarted the crew.
- **Fix:** CI check: a decoy-server test holds the launch guard.
- **Status:** applied: guard on `main` (#1482), live after the next release
  install.
- **Linked issue/PR:** #1475
