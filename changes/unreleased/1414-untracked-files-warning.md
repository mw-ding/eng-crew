---
type: added
issue: 1414
pr: 1676
date: 2026-11-11
box-skill: none
---

`scripts/check-repo.py` now warns on stderr when a git work tree has non-ignored untracked files, naming each one: its path checks (deliverables and the rest) read `git ls-files`, so a run before `git add` silently skipped new files. Ignored files stay quiet, the exit code is unchanged (no new gate), and once the files are added they are checked as usual.
