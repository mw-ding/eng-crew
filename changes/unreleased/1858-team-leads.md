---
type: added
issue: 1858
pr: TBD
date: 2026-11-13
box-skill: none
---

A team runs one lead per pool: `mdstack up --team` records each repo in `<team-root>/team.json` and ensures one `(team, pool)` lead per enabled pool through the first repo whose render, pause and ownership allow it (a repeat run starts none), with its record, inbox, status and brief at the team root. Every repo's route hands it messages carrying that repo's `context` envelope; a repo's watcher sees, parks and retries only its own messages, and the lead's `$CREW_PROJECT` is the team file, so a command without the message's project refuses for a multi-repo team. The three lead briefs gain a team-pool paragraph. Team runs take a team-global run ID and window slot under one team-root lock; their window names carry the repo tag (`ben-42-<owner>__<repo>`), their worktrees are `<worktree-root>/<owner>__<repo>/<run-id>/`, their run records add `run_id`, `context`, `project`, `checkout` and `handoff` (`mdstack spawn --handoff`, kept through the spawn queue), and a restart in place takes a new run ID. In a team, `mdstack kill` stops a window only at the run's recorded slot and pane, removes a worktree only under its own repo's tag and releases only its own repo's allocation. One-repo names, paths, records and outputs are unchanged.
