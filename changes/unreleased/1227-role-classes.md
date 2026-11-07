---
type: added
issue: 1227
pr: TBD
date: 2026-11-07
box-skill: none
---

Role classes (team spec REQ-20 to REQ-22): every role definition declares its `class` (`owner-facing` seat or `internal` staff) and `seat`, internal staff declare an `escalation` path ending at the owner-facing role holding their seat, and each registry names exactly one team head. `crew-roles.py` validates them. The engineering head, the coordinator, holds the `cto` seat; the other roles are internal staff under it. The protocol now states that only owner-facing seats deliver owner asks, and team spec Q1 is settled.
