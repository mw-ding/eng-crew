---
type: fixed
issue: 1352
pr: TBD
date: 2026-11-08
box-skill: none
---

The CI `links` job no longer fails on a transient lychee download error. It installs the pinned lychee release (version and sha256 explicit in the job's `env`) from an `actions/cache` keyed on both, and on a cache miss retries the download up to 5 times with backoff, verifies the checksum, then runs the same offline link check. A broken link, an exhausted retry or a checksum mismatch still fails the job, the last two with a clear `::error::`.
