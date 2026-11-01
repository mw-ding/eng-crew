---
type: fixed
issue: 384
pr: 385
date: 2026-11-01
box-skill: none
---

`crew spawn` and an in-place `crew restart` now pass `--add-dir <git common dir>` to every Codex role window, in every permission mode, next to the state dir. A linked worktree keeps its refs and objects there, so a host sandbox that allows writes only under the working directory and `--add-dir` paths no longer stops a Codex builder from creating a branch, committing or pushing.
