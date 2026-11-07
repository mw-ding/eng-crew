---
type: fixed
issue: 1089
pr: 1159
date: 2026-11-06
box-skill: none
---

`crew upgrade --version` (and `crew bootstrap --version`) now finishes with a verified record when an earlier `--version --dry-run` or a busy-pass timeout already extracted the version directory. Before, `fetch` refused any existing version directory, and its "run its bootstrap directly" hint recorded the install with `bundle_sha256: null` and no `transport`; under a `url` or `mirror` source, plain `crew upgrade` then refused as a source change and `--version` refused because the directory existed, until an owner deleted it by hand (found by the M25 A20 run). `fetch` now fetches and verifies the release again into a staging directory and reuses the existing directory only when its files match (interpreter caches aside), passing the digest and transport on; a directory that differs is refused and left in place. The upgrade it starts skips the source-change refusal for that just-verified bundle and re-records a record that lost its digest or transport instead of reporting `no changes`. The A20 campaign step now expects the retry to apply with the digest and transport recorded.
