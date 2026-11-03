---
type: changed
issue: 627
pr: TBD
date: 2026-11-02
box-skill: deferred to #140 (tmux synthesizer brief only)
---

`crew train build` keeps approved PRs that change the same paths together in one train, in the dependency then approval order the synthesizer supplies, and drops a member only when its merge actually conflicts (`reason=conflict`). It no longer defers clean overlapping members with `reason=overlap` for a merge-up after the train. Train CI still tests the combined result, so the land gate is unchanged. The tmux synthesizer brief and the crew train docs say the same (crew scheduler design S9, #587).
