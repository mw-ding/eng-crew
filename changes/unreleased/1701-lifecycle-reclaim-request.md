---
type: fixed
issue: 1701
pr: TBD
date: 2026-11-12
box-skill: none
---

The builder lead now treats a `lifecycle` `reclaim` work event as a request to remove that builder rather than a notice that it is gone. It runs its pool's `mdstack kill WINDOW`, reports a refusal as `lead-fault` and marks the id done only after the window and run record are gone. Before this, the lead brief named no action for the event, so a merged PR's close-out reached the lead and was acked, but the finished builder kept its slot until a manual terminal re-send (#1701's four windows).
