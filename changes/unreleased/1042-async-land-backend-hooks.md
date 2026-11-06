---
type: fixed
issue: 1042
pr: 1162
date: 2026-11-06
box-skill: none
---

A non-GitHub backend can bind the asynchronous land by config alone: the manifest's `[land]` table now takes `change_placeholder` (the token `crew land` fills with the change id, default `n`), `head_guard = false` (the backend's land has no head-match flag; the head re-read before the request still holds) and a `[land.status]` table mapping native status output to `none`, `queued`, `landing`, `landed` or `failed`, with the new conditional `change.read-landed` reading the revision when the status line has none. Output no declared pattern matches still reads unknown and never requests a land, and `crew land` refuses a `change.land` without `<head-sha>` unless `head_guard = false` is declared. GitHub stays sync and unchanged.
