---
type: added
issue: 1218
pr: 1242
date: 2026-11-07
box-skill: none
---

New `actions/` contract, documentation only: `actions/README.md` defines the twenty generic actions (A1–A20) roles use to coordinate, each with its semantics, inputs, outputs and the six outcomes `completed`, `pending`, `stale`, `refused`, `failed` and `unknown`, plus the capability declaration and CloudEvents/CDEvents event names; `actions/cli.md` fixes the `crew action` command names, arguments, exit codes and JSON output; `actions/mapping.md` maps each action to how tmux, herdr and Grok Bot carry it out today, with gaps marked. No command implements it yet (M32), and no gate, marker or label changes.
