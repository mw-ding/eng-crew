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
default branch as `crew/train-<n>` (a PR that conflicts is dropped), runs
the local checks, pushes the branch with a draft train PR and waits for CI
after a grace period, since `gh pr checks` fails until checks register.
`crew train land <n>` lands each member with `--match-head-commit`, in
order, only while the default branch is still the train's tested state, the
head is the tested head and a pass verdict is at head; it posts a merge
record citing the train branch, SHA and CI run, stops at the first miss,
then closes the train PR and deletes its branch. `crew train bisect` is not
built yet. The tmux synthesizer brief uses the train for two or more PRs
waiting to land, `docs/runtimes/tmux.md` documents it, and
`scripts/test-crew-train.py` covers it with a fake `gh` and a logging `git`.
The protocol §7 and gate registry wording follow in part 2. Part of #110.
