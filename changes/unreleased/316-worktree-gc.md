---
type: added
issue: 316
pr: 1740
date: 2026-11-11
box-skill: pending the coordinator's mirror of templates/runtimes/session/coordinator.md
---

New `mdstack gc` sweeps run working copies that lifecycle reaping missed: a run record whose window is gone and a directory directly under `paths.worktree_root` that no run names. It is a dry run by default, listing each candidate as `keep` or `remove` with its reason. A copy is removable only when its PR is merged (the run's PR, else a merged PR whose head is the copy's `HEAD`, so a squash merge with a deleted branch still proves) and the C6 check finds nothing unlanded. It keeps live windows, claimed or referenced copies, recent orphans, nested worktrees, open or closed-unmerged PRs and unlanded or unreadable copies, with reasons. `--apply` re-checks each candidate, removes at most `--max` (default 10) with `git worktree remove` (never `--force`) or, for a builder's own copy, by deleting its directory, then drops the run's records through the kill path; a failed removal is reported and exits 1. `mdstack route` runs it with `--apply --max 5` on each backstop wake, so a lost `pr-merged` event no longer leaves a merged run behind. Session-runtime worker and probe worktrees now use the same `paths.worktree_root`. Git stays the only worktree provider: treehouse was considered and deferred, as recorded in the tmux and session runtime docs.
