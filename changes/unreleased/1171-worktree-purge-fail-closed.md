---
type: fixed
issue: 1171
pr: TBD
date: 2026-11-06
box-skill: none
---

`scripts/worktree-purge.py --apply` now fails closed. Before removing anything it checks that every `remove` row's work tree and parent are writable, and if any is not it names the paths, removes nothing and exits non-zero. A removal that still fails is reported as `failed` with git's error, stops further removals, skips `git worktree prune`, reports an `orphan` when git dropped the admin entry anyway, and exits non-zero; the summary reads `removed N, failed M, kept K`. Every run also lists `orphan` rows, a directory under a scanned root (each worktree's parent and every `--root`) whose `.git` names a missing gitdir. Before this, a failed `git worktree remove` was counted as `kept`, the run exited 0, and 32 orphaned directories went unreported.
