---
type: added
issue: 882
pr: TBD
date: 2026-11-04
box-skill: none (reference docs only; no rendered doc or template changed)
---

Design note for release sources in `docs/bootstrap.md`, not yet active: an
optional `[install]` table (`source` = `github`, `url`, `mirror` or `git`;
default `github`, so unchanged profiles and install records stay as they
are), one verifier shared by bootstrap, upgrade and host prepare that checks
`SHA256SUMS` (with an optional pin on its digest) before anything is
extracted or run, a Git source verified by a pinned full commit rather than
as a checksummed bundle, a `transport` field in `install.json` shown by
`crew doctor`, and a host toolkit installed at the primary's pin, checked
file by file by `crew host check` and pruned by `crew host prepare --prune`.
`docs/profile.md`, the release update path and host readiness link to it.
Implementation slices B1 to B5 (#943 to #947) follow.
