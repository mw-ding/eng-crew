---
type: fixed
issue: 1100
pr: TBD
date: 2026-11-12
box-skill: none
---

`mdstack dequeue` no longer reports `no free slot` when a queued request is held back only because its pool's lead owns dispatch: it names the lead-managed pool and the operator path (`use the builder lead or CREW_POOL=builder`), keeps `no free slot` for a truly full band, says `none match --ref` for an unmatched ref and lists both reasons for mixed pools. Which requests dequeue may start is unchanged.
