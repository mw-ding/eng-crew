---
type: added
issue: 585
pr: 693
date: 2026-11-03
box-skill: none (rendered briefs unchanged; no template uses the release operations)
---

Make release a backend concern. `docs/interfaces.md` adds an optional `release` concern (`cut`, `approve-check`, `record-release`, `notify`), declared in the GitHub pack, mapped in `templates/backends/github.toml` and named in the default profile. An optional `[release]` profile table (`changelog`, `fragments`, `versioning`, `release_id = "tag" | "commit"`) defaults to today's behaviour; with it, `resolve` fails closed unless `approve-check` and `record-release` are kept. The release gate row is backend-neutral with the same satisfaction, and `docs/release.md` gives the GitHub binding (unchanged `release.yml`) plus a commit-hash reference binding covering the version pin, update path and rollback. `scripts/changelog-cut.py` no longer loads `check-repo.py`, takes paths from `--project` or flags, and accepts fragments with only `type`; eng-crew's own cut output is byte-identical.
