---
type: added
issue: 299
pr: TBD
date: 2026-11-04
box-skill: deferred to #140
---

Add run-blocker intake cards (M24 T7, `docs/triage.md`): `crew feedback --class SLUG --summary TEXT [--window NAME]` files a `runtime-blocker` card in `<owner>/eng-crew` (or `--repo`), prefilled from the window's run record (Source, role, engine, launch args) and redacted per spec R1 (tokens, emails, `<state-dir>` / `<worktree>` / `<home>` paths). When an open card already has that Failure class, it comments there instead, and it files nothing if it cannot list the cards. `docs/self-improve.md` adds the `runtime-blocker` trigger and recipe, the intake card lists the trigger, and the tmux coordinator brief tells the coordinator to report a crew defect in the same turn, unasked, without editing eng-crew.
