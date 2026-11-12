---
type: changed
issue: 1726
pr: 1763
date: 2026-11-12
box-skill: none
---

The negative-control section of `templates/evidence/cli-exit-stdout.md` now states its N1 requirement without Git: a throwaway snapshot of the guarded paths at the checked head, plus what the guard needs to run. A partial copy must name every copied path and dependency, keep their content at the head except for the mutation, and be recreated on verifier replay. The `git archive` setup stays as a labelled Git example. N1/N2 semantics, verifier replay and evidence acceptance rules are unchanged.
