# Contributing

This repo is the reviewed source of truth for the crew framework. Changes arrive
by PR, built by the crew through the normal pipeline (spec R7). This page is the
iteration process.

## From lesson to PR

1. **Record the lesson.** Write a dated entry under
   [docs/lessons/](docs/lessons/README.md) in the documented entry format, with
   its evidence, impact, proposed fix and status.
2. **Raise an issue.** The coordinator turns each actionable lesson into an
   issue with a goal, acceptance criteria and a link to the spec. Link the issue
   from the lesson entry.
3. **Land it by PR.** The builder opens a non-draft PR that closes the issue. The
   normal review loop applies: CI, review, validation, then merge by the
   synthesizer. Update the lesson entry's status and linked PR in the same PR.

Protocol and template changes follow the
[protocol freeze](docs/protocol.md#protocol-freeze): milestone batches,
next-milestone issues for lessons, and a gate-contract exception for fixes to
gates blocking merges now.

## Spec changes

Changes to `docs/specs/framework.md` use the `crew:spec` label. They get a review
pass only, and they merge only after the user gives the merge-ok steering
command, the `/crew merge-ok` command.

## Two copies, one change

The box skills are the **live** copies the bots load. This repo is the
**reviewed** copy. Any change to either must be mirrored to the other in the same
change (spec R4):

- A change here needs a matching edit to the box skill copy.
- A change made to a box skill first needs a PR here that mirrors it.

Say in the PR which way it was mirrored, or that there is no box skill change.
Templates are not copied by hand: the live copy is the
[renderer](scripts/README.md#renderer) output for the live profile, deployed by
the coordinator. A PR that changes `docs/protocol.md` or `templates/` carries
the `crew:needs-mirror` label, and the merge gate holds until the coordinator
posts the box-skill mirror comment, which records the deploy and a clean
[drift check](scripts/README.md#skill-drift-check-coordinator) at that commit,
and removes the label
([mirror hold gate](docs/runtimes/grok-bot.md#mirror-hold-gate)).
[Lighter-lane PRs](docs/protocol.md#6-duties-on-wake-all-roles) never get
`crew:needs-mirror`.

## CHANGELOG

Every PR records its change as a fragment instead of editing
[CHANGELOG.md](CHANGELOG.md): one new file `changes/unreleased/<issue>-<slug>.md`
(lowercase slug) with front matter, then one paragraph of entry text, the
change:

```markdown
---
type: fixed
issue: 123
pr: 456
date: 2026-10-31
box-skill: none
---

What changed and why, in one paragraph.
```

- `type`: `added`, `changed`, `removed`, `fixed` or `security`, the Keep a
  Changelog heading the entry goes under.
- `issue`: the issue number, as in the file name.
- `pr`: the PR number. Write `TBD` until the PR opens, then fill it in with a
  follow-up commit.
- `date`: `YYYY-MM-DD`, the merge date in America/Los_Angeles; for an unmerged
  PR, the date it was written.
- `box-skill`: whether the box skill copy was mirrored, for example `none` or
  `deferred to #140`.

Use no relative links in the entry text: their paths break when it moves into
`CHANGELOG.md`. `scripts/check-repo.py` checks every fragment's format.

At the cut, `scripts/changelog-cut.py <version>` turns each fragment into one
entry, `<text> (issue #<issue>, PR #<pr>, <date>) Box skill copy: <box-skill>.`,
so every entry still has its change, date, PR number and box skill status
(spec R5). It puts them under their headings in the new version section,
together with any entries already under `[Unreleased]` (those stay valid),
then deletes the fragments. It refuses a fragment that is malformed or still
says `pr: TBD`, and `scripts/release-check.py` refuses a release while any
fragment is left.

## No secrets

Never commit tokens, API keys, auth headers, email addresses, private chat
quotes or real box paths (spec R1). Refer to credentials by mechanism only, and
use placeholders such as `<owner>/<repo>` and `<state-dir>` (spec R2). Use role
names such as coordinator, builder, reviewer-validator and synthesizer.

## Decisions needing the user

When work is blocked on a decision only the user can make, the coordinator labels
the item `crew:needs-md` and raises it with:

- a recommended default, and
- a deadline, after which the default applies unless the user says otherwise.

Requests are batched into one digest per day rather than sent one by one. This
keeps decisions from stalling the pipeline for hours (see
[the bottleneck analysis](docs/lessons/2026-10-19-bottlenecks.md)).

## Checks

<!-- Script usage for local checks is added here later. -->

CI runs markdownlint and an offline link check on every PR and on `main`.
