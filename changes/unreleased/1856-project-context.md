---
type: added
issue: 1856
pr: 1866
date: 2026-11-13
box-skill: none
---

Team files gain five closed per-repo project keys, `control_item`, `labels`, `milestones`, `doc_home` and `flavor` (a table with only `name` that may only tighten the team's flavor, refusing a looser knob or cap with the key and the source of the floor). `labels` renames state tags on the tracker, read and written through by `mdstack poll` and `mdstack route`. A project's identity is its resolved team and canonical repo, a one-repo `config.toml` deriving the team `repo:<owner>/<name>`; aliases, symlinks and an omitted selector give one identity. `mdstack poll` and `mdstack send` stamp a closed `context` work envelope (team, project, repo, item, change, head, pass, round, `null` when absent) on wake records and inbox messages, `mdstack send --context` refuses a foreign one, and `mdstack route` refuses a malformed, foreign or conflicting envelope, an item or change read from another repo, or an envelope-less team-file record not bound to a run in that repo, before any spawn, post or handoff. Markers, status lines and one-repo resolution are unchanged. **Breaking:** a team file listing one repo in two sections, or setting `merge_grant` or `merge_grant_scope` under `[team.runtime.options]`, now fails to resolve. Migration: keep one section per repo and move a landing grant into each `[repos.<name>]` it covers.
