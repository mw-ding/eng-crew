---
type: added
issue: 934
pr: 991
date: 2026-11-04
box-skill: none (config tool and reference docs only; no rendered template change)
---

`crew-config.py sensitive --diff` reads a `git diff --no-renames` unified
diff on stdin and classifies it (#879 slice B2): path rules run on every old
and new path, and `[[sensitive.content]]` rules match added and removed
lines, reported as `content` records (rule, path, side, line) beside
`matches`. Hunk counts bound each hunk, so a changed line that looks like a
header is still content. An empty or malformed diff, a rename or copy header,
a file block cut inside its header or a quoted path exits 3 (classification incomplete), never a clean result.
Profiles without content rules print the same `label` and `matches` as
before; call sites still pass path lists until slice B3.
