---
type: added
issue: 454
pr: 456
date: 2026-11-01
box-skill: coordinator deploy required
---

The tmux runtime detects approved default-branch merge-ups and routes one fresh recheck session to inspect resolution hunks, rerun acceptance checks and post a merge-up re-approve at the new head. Non-mechanical resolutions return to full review and validation; the approval round and merge gates stay unchanged.
