---
type: changed
issue: 839
pr: TBD
date: 2026-11-04
box-skill: none (docs-only)
---

The onboarding runbook's tmux prerequisites move verbatim into a new
`docs/runbooks/tmux-onboarding.md` operator module (M26 modular organization,
first slice); the runbook keeps the `tmux prerequisites` heading as a link to
it, the parent tmux runtime introduction and the unmoved setup, run and
troubleshooting steps; the module gets its manifest, inventory and docs index
rows; no rule, gate, marker or default changes.
