---
type: changed
issue: 502
pr: 519
date: 2026-11-01
box-skill: coordinator mirror required
---

Reviewer bindings gain delta re-review of builder-resolved base updates with independent validation and a new head-pinned verdict, and record the reviewed base SHA. Approved merge-up events route to the synthesizer for patch identity rather than an automatic reviewer session. Coordinator dispatch never sends a change back solely for being behind and treats overlap as a risk signal, serializing only semantic dependencies, shared mutable external state or incompatible migrations. Final slice of #502.
