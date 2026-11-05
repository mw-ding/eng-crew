---
type: added
issue: 935
pr: TBD
date: 2026-11-05
box-skill: deferred to #140
---

Content rules for the sensitive class are now in force (#879 slice B3).
`change.read-diff` is a conditional operation: the GitHub manifest declares
it and the backend map binds it to a `git fetch` of the PR head and a
`git diff --no-renames` against the merge base, and `resolve` requires it
only when a profile declares `[[sensitive.content]]` rules. `crew-config.py
sensitive --paths-only` classifies an issue's named paths at triage with
path rules only, so content rules no longer stop triage. The tmux builder
and Grok Bot builder briefs pipe the worktree diff to `sensitive --diff`
when content rules exist, the tmux coordinator uses the backend's
`read-diff` and `--paths-only` at triage, and the triage template passes
`--paths-only`. The protocol Sensitive class wording is operative: an owner
override covers its recorded path matches and its recorded content matches
by rule and path, and a new pair on any push needs the owner's
reconsideration. Profiles without content rules classify as before.
