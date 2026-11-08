---
type: fixed
issue: 1339
pr: 1371
date: 2026-11-08
box-skill: none
---

`mdstack route` no longer kills the synthesizer on `pr-merged` while it is still checking the default-branch CI run at a direct land's merge commit. A synthesizer started with `--pr <n>` gets its first PR from its spawn arguments, not an inbox land request, so the merged close-out saw no pending land and reaped it, and a red main after a direct land went unreported. Close-out now keeps a synthesizer whose spawn PR is the merged one until its status has `done: #<n>`, `blocked: #<n>` or `blocked: main red after #<n>`; its later `done:` line reaps it as before.
