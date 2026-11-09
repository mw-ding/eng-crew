---
type: fixed
issue: 1093
pr: 1451
date: 2026-11-08
box-skill: none
---

`mdstack poll`'s triage scan no longer queues a second `triage-p0` coordinator wake when the owner answers the triage record of a P0 item. A recorded item leaves `triage/queue.json`, so owner feedback re-queued it as an unseen P0 candidate; the wake now fires only for a `new` entry, an item with no `pass=triage` record yet, and owner feedback is still queued as `owner-feedback`.
