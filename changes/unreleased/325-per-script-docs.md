---
type: changed
issue: 325
pr: TBD
date: 2026-11-01
box-skill: none
---

Per-script docs replace the shared usage table in `scripts/README.md`, a merge
hotspot that nearly every scripts PR edited (#325, part 1 of 2; part of #110).
Each script's usage now lives in its module docstring, and `--help` prints it
(`crew --help` and `crew <cmd> --help` too); `scripts/README.md` keeps a short
guide and the long-form sections. A new `check-repo.py` check, `script-docs`
(rule `script-doc`), fails when a script under `scripts/` has no module
docstring, or a script you run or a `crew` command has no `Usage:` line.
`test-check-repo.py` proves that two branches that each add a script with its
docs merge with no conflict. Index files (deliverables, required docs, docs
index) follow in part 2.
