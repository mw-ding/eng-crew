---
type: changed
issue: 1425
pr: TBD
date: 2026-11-08
box-skill: deferred to #140 (profile mirror_deferral)
---

`mdstack train build` decides a train's path from its surviving members before any push and records it as `path` in the train record and `train-report`: `train` for two or more (or one with no drop), `none` when every PR dropped, and `direct` when drops leave exactly one member on the default branch under `runtime.options.lone_pr_land = "direct"`. A `direct` build pushes no train branch, opens no train PR and waits for no CI. It closes the record with `path_reason` `collapsed-to-direct: train <n> dropped #<pr> (<reason>)`, routes the dropped PRs to merge-up at once and prints `direct pr=<pr> head=<sha>`. The synthesizer then lands that PR by the direct land rule, with every §7 gate at its head and the lone-ready re-survey under the land lock, and its merge record copies the collapse reason. With `lone_pr_land = "train"` nothing changes. `mdstack train check` gains a `train-merge` gate, a survey-time pre-filter that runs the build's conflict and patch-portability checks for each PR alone on the current default branch with `git merge-tree`, so failing PRs go to merge-up before a train forms.
