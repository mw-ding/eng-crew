---
type: changed
issue: 653
pr: 660
date: 2026-11-02
box-skill: pending coordinator mirror
---

CLI evidence for a command that only runs against test fakes (a fake tmux, a fake `gh`, a temp git origin) may use a named test command as its repro pair, when no real-environment run is possible without the fakes. The test must invoke the changed command and assert its exit code, stdout and stderr; the validator re-runs it at head and diffs it like any other pair. The verification CLI row and Q2, protocol §3, the tmux builder and reviewer briefs, Grok Bot B1, the reviewer-validator and V2 watch prompts, and their render and parity fixtures carry the rule.
