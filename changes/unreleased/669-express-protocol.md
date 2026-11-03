---
type: added
issue: 669
pr: TBD
date: 2026-11-03
box-skill: deferred (tmux mirror deferral; Grok Bot runs express items in the crew lane)
---

Write the express lane into the protocol. §3 adds express resolution (`class-flavor --express`, tightening and sensitive/spec exclusions, `review = off` only for express) and the builder's selfgate record with its `pass=selfgate` hidden line. §4 adds the `selfgate` pass and the `crew:express` state tag. §7 and the gate registry add the express self-gate, which replaces formal approval for an express change and keeps every other gate. The portable spec §3 records the scoped I1 and I2 exception, and `docs/architecture.md` adds the label and pass rows. Until the routing build issue lands, an express change is still reviewed as usual.
