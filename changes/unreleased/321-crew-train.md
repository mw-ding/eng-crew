---
type: added
issue: 321
pr: 326
date: 2026-11-01
box-skill: deferred to #140
---

`crew train`, a merge train for the tmux runtime (part 1 of #321): approved
PRs are tested together once, then land with no catch-up between them, in
place of the merge queue GitHub does not offer private repos on GitHub Free.
`crew train build <pr>...` merges each PR head onto the freshly fetched
default branch as `crew/train-<n>` in a temporary clone that ignores local
merge attributes, so a local `merge=union` cannot hide a conflict GitHub
would hit (a PR that conflicts is dropped). It runs the local checks,
pushes the branch with a draft train PR and waits for CI after a grace
period, since `gh pr checks` fails until checks register.
`crew train land <n> <pr>` lands the next member with
`--match-head-commit`. The synthesizer re-runs the whole §7 check at that
head right before each call, and `land` itself stops unless the default
branch is still the train's tested state, the head is the tested head, a
pass verdict and merge permission are at head, there is no
`crew:escalated`, `crew:changes`, blocking `crew:hold`, open rereview or
open hold-until, and GitHub reports the PR mergeable. It posts a merge
record citing the train branch, SHA and CI run; a stop or the last member
closes the train PR and deletes its branch, and `crew train close` ends a
train early. `crew train bisect` is not built yet. The tmux synthesizer
brief uses the train for two or more PRs waiting to land,
`docs/runtimes/tmux.md` documents it, and `scripts/test-crew-train.py`
covers it with a fake `gh` and a logging `git`.
The protocol §7 and gate registry wording follow in part 2. Part of #110.
