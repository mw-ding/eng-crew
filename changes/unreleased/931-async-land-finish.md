---
type: added
issue: 931
pr: 1005
date: 2026-11-05
box-skill: pending (protocol §7 wording; see the PR's mirror status)
---

Asynchronous land, persisted intent and restart (#873 slice B3). `crew land
request` records a land intent keyed by change and head before its first
status read, and `landed` prints the merge record's landed revision and a
`pass=merge` marker with `sha=` the checked head and `landed=` the landed
revision. New `crew land resume` reads the status of every recorded intent
on a wake and never requests: an in-flight land resumes polling, a landed
one prints its pending record, and a never-requested one is dropped. New
`crew land done` clears an intent only once it is marked landed. Protocol
§7 states the asynchronous land record and restart rules.
