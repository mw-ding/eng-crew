---
type: added
issue: 185
pr: TBD
date: 2026-11-01
box-skill: coordinator deploy required
---

Synthesizer templates now maintain one gate-status review per change listing all unmet merge gates and who owes each item, update it across heads, clear it when satisfied, and wake the coordinator. Gate rules remain unchanged; rendered fixture checks cover the item list and reporting contract.
