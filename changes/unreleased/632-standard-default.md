---
type: changed
issue: 632
pr: TBD
date: 2026-11-03
box-skill: pending coordinator mirror
---

**Breaking:** An unset project flavor now resolves `standard` (thin review, validation for behaviour changes only) instead of `thorough`, still flagged as `flavor.name = "standard"  # core (unset: flagged)`. Rendered briefs for unset projects now carry the standard `Flavor:` baseline line, and `item-flavor.py`, class matching and class validation use the same default. Item records and class rules still raise rigor; `thorough` stays the preset for releases, security and gate-contract work, and the flavor docs recommend a `thorough` class for gate-defining paths. Unset all of 2026-11-02, validation found problems after a passing review in 2 of 217 rounds (0.9%). Migration: set `[flavor] name = "thorough"` to keep the old behaviour.
