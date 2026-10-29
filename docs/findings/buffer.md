# Findings buffer

The live buffer. How to append, when to batch and who owns it are in
[README.md](README.md). Entries use the template there.

## Entries

### Builder per-PR watch (B2) missing or not verified

- **Date:** 2026-10-23
- **PR / repo:** this repo (eng-crew), PRs #35, #38 and #41. See
  [builder-watch-attach](../lessons/2026-10-23-builder-watch-attach.md),
  [watch-handoff-first-run](../lessons/2026-10-23-watch-handoff-first-run.md)
  and [merge-gate-watch-race](../lessons/2026-10-23-merge-gate-watch-race.md)
- **Smell:** The builder's B2 watch was missing, unverified or unreadable. On
  #35 B2 never attached and the PR stalled about 62 min. On #38 the
  `pass=watch` marker carried a 7-char SHA, so the reviewer cross-check could
  not match it. On #41 the PR merged before the B2 hand-off reached the
  builder's parent turn, so no watch or marker existed.
- **Count:** 3
- **Proposed fix layer:** architecture: create and verify B2 in the same turn
  that opens the PR, so no hand-off can lag behind a fast merge. The fixes
  shipped so far are prose plus a merge gate: the verified hand-off (#36, fix
  PR #37), one watch identifier and full-SHA markers (#39, fix PR #41), and the
  merge gate requiring the `pass=watch` marker (#43, fix PR #45).
- **Status:** fixed by #37, #41 and #45 (all `documented` in the lessons).
  Seeded as a worked example: three sightings of one smell became three lesson
  files and three fix PRs; under this buffer they would have been one batch
  issue.
