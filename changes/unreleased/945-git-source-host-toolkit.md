---
type: added
issue: 945
pr: 1000
date: 2026-11-04
box-skill: none (scripts and reference docs; no rendered template change)
---

Release sources slice B3: `[install] source = "git"` works in `crew
bootstrap --version` and `crew upgrade --version`. The tag is fetched into
a temporary bare repository with no checkout and no hooks, refused unless it
peels to the pinned `git_commit`, and only then built by that commit's own
`scripts/release-bundle.py`; the built bundle passes the same member,
`VERSION` and entry point checks before it moves into place, and
`install.json` records the commit. No `gh` call is made. Slice B4: with an
`[install]` table, `crew host prepare` sends the primary's `install.json`
(tag, bundle digest, transport) as a toolkit pin in the `prepare` and `seed`
calls, and the host installs that release into `toolkit/eng-crew-<v>/` from
the same source with the same verifier, staging it first and writing its
record (pin, digest, SHA-256 of every file) last; a verified existing
version is reused and a tampered or partial one is installed again; the
active version is replaced only after the new one verifies, so a refused
release leaves the previous install usable. Slice
B5: `crew host check` then adds a required `toolkit` row, from the `version`
call with the pin, that fails when the project pins no toolkit or another
tag on the host, or the version's record or any file hash differs; `crew
host prepare --prune` removes the toolkit versions and staging leftovers no
project on the host pins and lists them. Without `[install]`, host prepare
and check send no pin and print the same output as before.
