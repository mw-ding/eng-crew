---
type: added
issue: 930
pr: TBD
date: 2026-11-04
box-skill: none (a new crew command and reference docs; no rendered template change)
---

New `crew land status|request --pr <n> --head <head-sha>` for an
asynchronous land (#873 slice B2). It refuses a `sync` change backend and
runs the backend map's `change.land-status`, `change.read-head` and
`change.land`. `request` requests only on a `none` status at an unmoved
head, resolves a lost acknowledgement by reading the status back instead of
resending, then polls every `land_poll_interval` seconds until `landed`
(exit 0, landed revision printed) or `failed`, an unknown status or
`land_timeout` (`blocked:`, exit 1). It takes no land lock and builds no
train. The renderer now accepts the conditional `change.publish` and
`change.land-status` operations in `<op:>` tokens. Nothing calls the command
yet, and every sync backend, GitHub included, is unchanged.
