---
type: fixed
issue: 1367
pr: TBD
date: 2026-11-10
box-skill: none
---

Each crew fetch now resolves its own result: the shared fetch helper used by `mdstack spawn`, merge trains (including the fetches between member lands) and uninstall fetches into an invocation-unique private ref (`refs/crew/fetch/<pid>-<random>`) with `--no-write-fetch-head`, an empty `--refmap` and `--no-tags`, resolves that ref and deletes it. Concurrent builder, reviewer, train and spawn fetches in one checkout therefore no longer read each other's `FETCH_HEAD` (a reviewer spawn refused as stale against main's head, #1367) or race on `refs/remotes/origin/*` (`incorrect old value provided`, which stopped a train, #1584). A real fetch failure still fails, and a changed PR head still refuses a stale spawn.
