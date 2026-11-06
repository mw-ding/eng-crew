---
type: fixed
issue: 1088
pr: TBD
date: 2026-11-06
box-skill: none
---

The Claude Code turn-end guard Stop hook now names the resolved bundle path, and `crew up`, `crew bootstrap` and `crew upgrade` re-point any existing crew guard for the same state instead of appending another. Before, `crew up` through the `paths.eng_crew` link added a second guard naming the link, and each upgrade added one for the new bundle, so `.claude/settings.local.json` no longer matched its `install.json` hash and every later `crew bootstrap` or `crew upgrade` refused with `target edited or unowned` (found by the M25 A20 run on #796).
