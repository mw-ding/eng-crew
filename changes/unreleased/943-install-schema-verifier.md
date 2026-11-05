---
type: added
issue: 943
pr: 975
date: 2026-11-04
box-skill: none (scripts and reference docs; no rendered template change)
---

Release sources slice B1: `crew-config.py validate` and `resolve` accept an
optional `[install]` table (`source` = `github`, `url`, `mirror` or `git`;
default `github`). They require `location` for `url`, `mirror` and `git`
(`https`, or `http` only to a loopback host, for `url`) and a full
`git_commit` for `git`, check the `sha256sums_digest` and `git_commit`
formats, and refuse a key the chosen source does not use. A new
`scripts/crew-install.py` holds the shared verifier (an optional pin on the
`SHA256SUMS` digest, exactly one matching entry, archive member checks,
`VERSION` and entry point, all before the bundle moves into place, with
nothing extracted before the checksum checks) and the `install.json`
`transport` record, where a record without one reads as `github`. No command
reads the table or calls the verifier yet; bootstrap, upgrade and host
prepare adopt them in slices B2 to B5. Without `[install]`, output and
records are unchanged.
