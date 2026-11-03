---
type: added
issue: 668
pr: 680
date: 2026-11-03
box-skill: none
---

Add the item-only `express` flavor preset (`review = off`, `validation = off`, `merge = auto`) and the `flavor.selfgate_engine` knob (`different` by default, or `same`). The validator rejects `express` as a project, class or custom base flavor, and `review = "off"` anywhere else still fails as `floor F4`. `crew-config.py class-flavor --express` applies the express knobs unless a path matches a tightening class, and reports `lane` and `tightening`. `item-flavor.py` accepts an `express` record that has a `Reason:` line, but never accepts `express` as a default. `docs/flavors.md` adds the preset and the scoped F4, I1 and I2 exceptions.
