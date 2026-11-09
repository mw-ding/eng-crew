---
type: fixed
issue: 1123
pr: 1506
date: 2026-11-09
box-skill: none
---

`mdstack doctor`, and so bootstrap's preflight and self-test, checks for `gh`, its logins and the GitHub repo checks only when a concern binds the `github` backend or the `[install]` source is `github`. A pack whose backends are all its own can now bootstrap from a staged release with no `gh` on `PATH`; doctor prints `gh not checked: no github backend or release source` instead. GitHub-bound installs still fail preflight without `gh`.
