---
type: changed
issue: 625
pr: TBD
date: 2026-11-03
box-skill: none
---

The reviewer lead now admits through `crew schedule decide --pool reviewer` instead of `crew reviewer-pool`'s own capacity check. Before each reviewer spawn, the dispatcher starts the pass only when decide admits its PR, and it releases the grant if the spawn fails. A deferral prints `crew: reviewer admission deferred: #PR REASON` and the request stays pending. A review held by a builder-lead call is granted on the next reviewer call, and the reviewer floor admits one pass under builder load. The scheduler snapshot now ranks a reviewer `work` event as the pass it starts: a new head, fix at head, merge-up, built PR or recheck escalation as a review, and a passing review as a validation. `crew reviewer-pool` no longer takes `--suites`.
