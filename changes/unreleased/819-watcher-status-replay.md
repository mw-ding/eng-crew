---
type: fixed
issue: 819
pr: 1375
date: 2026-11-08
box-skill: none
---

`mdstack watch` no longer replays a retained status file as fresh wakes. It used to reset a window's read offset whenever the run identity changed, so a lead restart (which keeps `status/<lead>.status`, and saves its record once without and once with the new pane identity) re-queued every historical `blocked:`/`delivered:` line, up to twice per restart. The offset now carries a SHA-256 digest of the read prefix in `wake/watch-state.json`: reading resumes at the offset while that prefix is unchanged, and starts over only for a file shorter than its offset or with a changed prefix (a new run's file, as in #369). `mdstack migrate` drops the digest of each status file it rewrites, so its recomputed offset is trusted.
