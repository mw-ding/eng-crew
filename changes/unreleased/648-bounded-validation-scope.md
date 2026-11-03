---
type: changed
issue: 648
pr: TBD
date: 2026-11-03
box-skill: pending coordinator mirror (reviewer templates)
---

Validation scope is bounded by default. A new rigor knob, `validation_scope` (`repo` · `bounded`), sets how far the validate pass reaches: `bounded` (every preset but `thorough`) runs the item's acceptance checks and only the checks covering the files changed at head, using the configured `builder.precheck` test command for those paths, and cites green CI at head for the rest. `repo` (thorough, or a custom flavor or class rule) adds the configured repo-wide lint and test commands. The tmux and Grok Bot reviewer briefs render the scope baseline and the configured commands instead of a fixed `scripts/check-repo.py` / `scripts/test-*.py` list; docs/flavors.md adds a validation cost note.
