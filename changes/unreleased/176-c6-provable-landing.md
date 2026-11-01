---
type: changed
issue: 176
pr: 295
date: 2026-10-31
box-skill: none
---

Runtime contract C6 provable landing: `docs/runtimes/README.md` C6 now
says teardown never removes a worktree unless its work has provably
landed (no uncommitted or untracked paths, and every commit on a freshly
fetched default branch, run branch or change head; a check that cannot
run counts as not landed) or the owner discarded it, with the reason and
the unlanded list recorded on the change or tracker item first.
`docs/runtimes/tmux.md` cites `crew kill`'s existing unlanded-work check
and `--discard --reason` (#172) as its C6 answer.
`docs/runtimes/grok-bot.md` declares a partial C6 gap: cleanup runs only
after a pass pushes or on `pr-merged` / `pr-closed`, with no landed check
before the delete. No code or routine change. Roadmap 15.3,
decision #160 row 3.
