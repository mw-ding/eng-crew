---
type: added
issue: 945
pr: TBD
date: 2026-11-04
box-skill: none (scripts and reference docs; no rendered template change)
---

Release sources slice B3: `[install] source = "git"` works in `crew
bootstrap --version` and `crew upgrade --version`. The tag is fetched into
a temporary bare repository with no checkout and no hooks, refused unless it
peels to the pinned `git_commit`, and only then built by that commit's own
`scripts/release-bundle.py`; the built bundle passes the same member,
`VERSION` and entry point checks before it moves into place, and
`install.json` records the commit. No `gh` call is made.
