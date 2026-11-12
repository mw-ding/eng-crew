---
type: added
issue: 1723
pr: 1756
date: 2026-11-12
box-skill: none
---

`hosts.<primary>.checkout = "command"` is accepted, so a primary on a non-git checkout (such as a virtual-filesystem monorepo) can read ready. `mdstack host prepare <primary>` runs the declaration under the primary's own `root` (`checkout/<owner>__<repo>.json`, argv with no shell and a checked exit) in place of the git fetch and writes the same receipt as a remote command checkout; `mdstack host check <primary>` reads that receipt, never runs the command, and prints `ok project checkout` in place of `project mirror` only when the declared path exists and is the profile's project checkout. Doctor and engine-login rows still gate ready. Git primaries and remote command checkouts are unchanged.
