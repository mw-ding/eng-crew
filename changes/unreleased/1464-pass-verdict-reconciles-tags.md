---
type: fixed
issue: 1464
pr: TBD
date: 2026-11-10
box-skill: none
---

A passing verdict after a changes round no longer leaves `crew:changes` on the PR for the synthesizer to refuse the land on (#1464, #1483). Before `mdstack route` forwards `review-approved` or an approved `ci-passed` to the synthesizer lead, it sets `crew:approved`, removes a superseded `crew:changes` or `crew:in-review` and reads the tags back, but only for a passing verdict at head from this runtime's reviewer (its login and signature). A failed readback keeps the event queued for the coordinator, and a replayed approval edits nothing. A stale, foreign or later changes verdict, a later formal changes request, an open rereview, a hold or an escalation leaves the tags alone, and the land gate still blocks on `crew:changes`.
