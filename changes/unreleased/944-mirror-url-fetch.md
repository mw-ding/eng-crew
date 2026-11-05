---
type: added
issue: 944
pr: 990
date: 2026-11-04
box-skill: none (scripts and reference docs; no rendered template change)
---

Release sources slice B2: `crew bootstrap --version` and `crew upgrade
--version` fetch from the profile's `[install]` source. `url` (an HTTP GET)
and `mirror` (a file copy) read `eng-crew-<v>.tar.gz` and `SHA256SUMS` from
`<location>/v<v>/`, make no `gh` call, and verify with the shared verifier
(optional `SHA256SUMS` pin, exactly one matching entry, member checks,
`VERSION`) before anything is extracted or run; a refused release leaves the
previous bundle, link and record untouched. `install.json` records a
`transport` (kind, location, `SHA256SUMS` digest, pinned) for those sources,
and `crew doctor` shows it in an `install source` row and skips the
latest-release query. Plain `crew upgrade` refuses when the profile's source
no longer matches the running bundle's record. `git` is refused until slice
B3. Without `[install]`, output and records are unchanged.
