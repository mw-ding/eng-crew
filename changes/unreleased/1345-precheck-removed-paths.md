---
type: fixed
issue: 1345
pr: 1573
date: 2026-11-09
box-skill: none
---

`crew-config.py precheck-scope` now classifies a changed path that is absent from the worktree at head (a deletion or a rename source) as `removed`: it gets no owners query and no targets and never counts as unowned, so a pure directory move runs the destinations' targets and a deletion-only change is `tests: n/a` instead of failing with exit 3. The output gains a `removed` list, and the builder brief's pre-review step 3 says to pipe every changed path from the worktree at head.
