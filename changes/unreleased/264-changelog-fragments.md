---
type: added
issue: 264
pr: TBD
date: 2026-10-31
box-skill: none
---

CHANGELOG fragments, part 1 (tooling and `CONTRIBUTING.md`): a PR records
its change as `changes/unreleased/<issue>-<slug>.md` (front matter `type`,
`issue`, `pr`, `date`, `box-skill`, then one paragraph) instead of editing
`CHANGELOG.md`. `scripts/changelog-cut.py` turns each fragment into an entry
under its Keep a Changelog heading in the cut section, together with any
entries already under `[Unreleased]`, then deletes the fragments; it refuses
a malformed fragment or `pr: TBD`. `scripts/release-check.py` refuses a
release while a fragment is left, and `scripts/check-repo.py --only
fragments` checks every fragment's format. `changes/**` is classified
internal. The process text for roles, release and the briefs follows in a
part 2 PR.
