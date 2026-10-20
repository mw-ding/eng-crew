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

## CHANGELOG

Every PR adds an entry to [CHANGELOG.md](CHANGELOG.md) under `[Unreleased]`: the
change, the PR number, and whether the box skill copy was mirrored (spec R5).

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
