---
type: fixed
issue: 1836
pr: TBD
date: 2026-11-13
box-skill: none
---

A held review no longer re-nudges the reviewer lead in a loop. `mdstack reviewer-pool` now writes the typed `waiting: #<n> owner|hold id=<id>` line itself, after its ack, for a review, validate, recheck or `work` request whose PR is live `crew:escalated` or `crew:hold`, and keeps the id pending. The lead backstop's wait fingerprint now uses only the polled PR's state, head and CI, plus its hold, owner answers and ask. Mergeability and verdict churn no longer wake a parked id, and poll catching up on a hold the dispatcher already saw becomes the new baseline. The #1833 incident's five re-nudges in about 15 minutes came from those wakes, not from the repeated acks; a hold release, CI or head change, owner answer or ask still wakes the id once.
