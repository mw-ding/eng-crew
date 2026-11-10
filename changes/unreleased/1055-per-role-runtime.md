---
type: added
issue: 1055
pr: 1586
date: 2026-11-10
box-skill: none
---

`runtime.options.role_runtime` (tmux and session) renders one role's brief from another runtime's templates, so a crew can adopt a runtime one role at a time, for example the session coordinator alongside tmux workers. The render swaps that role's registry template for `templates/runtimes/<runtime>/<role>.md` and fails closed on an unknown role, the selected runtime itself or a missing template; profiles without the key render byte-identically.
