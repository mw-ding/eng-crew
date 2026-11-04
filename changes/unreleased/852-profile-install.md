---
type: changed
issue: 852
pr: 864
date: 2026-11-04
box-skill: none (docs-only)
---

The onboarding runbook's `### Bootstrap (recommended)` subsection of Step 0
moves verbatim into the new module `docs/runbooks/profile-install.md` (M26
modular organization, seventh slice), with the verified-release and `--dev`
distinction, the dry-run and apply commands, the refusal and human-review
conditions, the expected outputs, the Grok Bot and tmux deployment
distinction and the remaining Steps 1–8; the runbook keeps the Step 0 and
Bootstrap headings and anchors as a link to it, and the module links the
still-unmoved manual fallback and onboarding steps; no rule, gate, marker or
default changes.
