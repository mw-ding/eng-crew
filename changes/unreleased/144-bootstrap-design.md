---
type: added
issue: 144
pr: 304
date: 2026-10-31
box-skill: none
---

Bootstrap design: `docs/bootstrap.md` answers the ten #144 questions,
with the alternatives considered for each. `crew bootstrap` runs from an
extracted, checksum-verified release bundle at a tag. It resolves the
config layers, proposing a project file when there is none (#191), and
runs `crew doctor` (21 preflight checks, each with a fix hint, failing
closed; includes the nested-sandbox quirk through `CREW_SANDBOX_ENV`).
It plans first (`--dry-run`), applies idempotent `crew:*`-only repo
fixers, renders once into the state dir and installs untracked pointers
per harness. It records `VERSION` and `install.json`, then self-tests.
The doc also has a per-runtime install-target table (Claude Code, Codex,
Grok Bot, tmux) with contract gaps, upgrade with role reload (#192),
uninstall as automated offboarding, secrets by mechanism, and a mapping
onto #165, #166 and #190–#194 plus proposed build issues. Indexed in
`docs/README.md`, classified as an install doc in
`docs/deliverables.md` and `scripts/deliverables.txt`, and listed in
`scripts/required-docs.txt`. No rule or gate changes. Roadmap 17.1.
