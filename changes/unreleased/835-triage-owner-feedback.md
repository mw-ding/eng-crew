---
type: added
issue: 835
pr: TBD
date: 2026-11-05
box-skill: deferred to #140
---

Owners can give feedback on any triage record, shadow or applied, by
replying on the item with `triage: accept`, `triage: reject <reason>` or
`triage: adjust priority=P2 type=bug`; a signed `[Ash/decision]` quoting the
owner's words and time counts the same, on the item or naming it on the
decision log. `crew poll` now queues an item for that feedback even after an
applied record placed it, and the triage sweep records it as
`owner-accepted`, `owner-rejected` or `owner-adjusted`, reverting or
correcting the applied record's reversible changes and backfilling relayed
answers it missed. `triage-metrics.py` counts the feedback in accuracy and
the override rate, reports it per sweep (`report --sweep`), and adds
`rolling`, which scores the newest 10 owner answers on applied records and,
below 8 accepted, proposes a return to shadow mode. In apply mode the first
sweep each day asks for 3 spot checks. No gate, flavor, merge-permission or
owner-config change.
