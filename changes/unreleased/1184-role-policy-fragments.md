---
type: changed
issue: 1184
pr: 1190
date: 2026-11-06
box-skill: none (every rendered brief is byte-identical)
---

Role policy shared across runtime templates is now authored once. The renderer replaces a template line exactly `<include:policy/<dir>/<name>.md>` with that fragment from `templates/policy/` (pack overlay first), renders its lines like the including file's and reports problems at the fragment's own file:line; one level only, so a nested, missing or inline include fails closed. The reviewer flavor-validation, delta re-review and pass steps, the builder build-pass, CLI evidence and fix-round blocks, the synthesizer gate, land-rule and merge-train sections, and the Grok Bot landing-authority input list now each live in one fragment, while wake, delivery and worktree lines stay in the tmux, session and Grok Bot templates. Every rendered brief for the default, tmux, session, parity-fixture and eng-crew profiles is byte-identical to before. markdownlint's MD029 (ordered list prefix) is off, since an include line splits a raw template's numbered list; rendered briefs keep their numbering.
