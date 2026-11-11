---
type: fixed
issue: 1684
pr: 1687
date: 2026-11-11
box-skill: none
---

The campaign lint now decides where an `exit` or `return` stops by one stated termination model instead of per-form patches: `exit` ends the step only in the step's own shell, so an `exit`, `return` or call to a helper that can `exit` inside a subshell, pipeline, background job or command substitution is refused by name. This closes the two forms left open by #1677 (an exiting helper called in a pipeline, a backgrounded `exit` in a handler group), and `docs/campaign-harness.md` documents the model. A04, A25 and A31 fixture steps were restructured with unchanged oracles.
