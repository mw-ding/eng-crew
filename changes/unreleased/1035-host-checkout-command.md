---
type: added
issue: 1035
pr: TBD
date: 2026-11-10
box-skill: none
---

`mdstack host prepare` supports a host whose project checkout is made by a declared command instead of a git mirror: with `hosts.<name>.checkout = "command"`, the host runs the argv it declares in `<root>/checkout/<owner>__<repo>.json` (no shell, checked exit, never sent over SSH), requires the declared path to exist, then makes its worktree and state directories and installs the toolkit as before. `mdstack host check` reports such a host ready once the command has run, through a `project checkout` row in place of `project mirror`. Mirror-based hosts send and check exactly what they did before.
