# Release workflow and update path (design)

How a version of the [deliverables](deliverables.md) is cut, approved and
published, how installed environments take it, and how to roll back
(roadmap R1.1, [#145](https://github.com/mw-ding/eng-crew/issues/145);
umbrella [#110](https://github.com/mw-ding/eng-crew/issues/110);
[portable spec P9](specs/portable.md#2-requirements)).

This page adds no rule, gate, cap, marker field or label. Its release gate
row is in the [gate registry](protocol.md#gate-registry), added by
[R1.3](#follow-up-issues) under the
[gate contract](protocol.md#gate-contract). Implemented: the release
workflow ([#218](https://github.com/mw-ding/eng-crew/issues/218), PR #243),
the bundle build ([#236](https://github.com/mw-ding/eng-crew/issues/236),
PR #245) and the bundle attach
([#246](https://github.com/mw-ding/eng-crew/issues/246), PR #248). `v1.0.0`
was tagged and released by hand on `b2144a2`, and `v2.0.0` was cut through
`release.yml` after the CHANGELOG cut in PR #273 (both
[#219](https://github.com/mw-ding/eng-crew/issues/219)).

## Decisions

Release on cut merge is the approved design
([#274](https://github.com/mw-ding/eng-crew/issues/274)); the workflow
implementation follows in [#387](https://github.com/mw-ding/eng-crew/issues/387).
Until it lands, the existing dispatch workflow remains the manual fallback.

| Question | Choice | Alternatives considered |
|---|---|---|
| Trigger | Landing the CHANGELOG cut PR: `release.yml` runs on a `push` to `main` touching `CHANGELOG.md`; `workflow_dispatch` remains for dry runs and manual fallback | Milestone close: an outward action as a side effect of tracker hygiene, and not every milestone is a release. A release label: overloads `crew:*` state tags, which the protocol keeps for change state |
| Who starts the release | The synthesizer lands the approved cut PR; the workflow completes the release without a coordinator dispatch or run watch | A separate dispatch after landing the cut: an extra owner action |
| Who approves | The owner's per-PR merge-ok on the cut PR at its head (`pass=steer cmd=merge-ok sha=<head>`); the publish job verifies it and the `RELEASE_OWNER` actor check | A standing grant: never covers a cut PR |
| CHANGELOG cut | A normal crew PR runs `scripts/changelog-cut.py <version>` ([#217](https://github.com/mw-ding/eng-crew/issues/217)) and lands through §7 with the owner's per-PR merge-ok to trigger the release | The workflow committing the cut to `main`: a direct push bypasses review and breaks invariant 4 (only the synthesizer lands). A workflow-opened PR: PRs opened with the workflow token start no CI, so §7 could never pass |
| What the workflow writes | A tag, a GitHub Release and the release-issue notice and closure; never a commit | none |
| Release workflow PR | `crew:sensitive` ([#184](https://github.com/mw-ding/eng-crew/issues/184)); until that class lands, the owner's per-change merge-ok is stated on the PR | Standing doc-only merge-ok: never covers `.github/` |

## Steps

1. **Release issue.** The coordinator files "Release vX.Y.Z" with the bump
   reason: the largest change class among the `[Unreleased]` entries
   ([versioning](deliverables.md#versioning)).
2. **Cut PR.** A builder runs `changelog-cut.py X.Y.Z` on a branch; the diff
   cuts `CHANGELOG.md` and consumes the fragments under `changes/unreleased/`.
   Its body says `Closes #<release issue>`. It goes through review and the
   [§7 merge gate](protocol.md#7-merge-gate-synthesizer); the owner gives
   per-PR merge-ok at the cut PR's head (`pass=steer cmd=merge-ok sha=<head>`).
   The standing grant never covers a cut PR. CI validates and builds the
   bundle on the real cut before it can land.
3. **Trigger.** The synthesizer lands the cut PR. `release.yml` runs on
   `push` to `main` touching `CHANGELOG.md`. It proceeds only for a new top
   versioned section `[X.Y.Z]`, empty `[Unreleased]` and no existing
   `vX.Y.Z`; otherwise it exits green with a one-line summary.
4. **Validate job** (read-only token). At the pushed merge commit it fails
   closed unless:
   - the top versioned `CHANGELOG.md` section is `[X.Y.Z]` and
     `[Unreleased]` above it is empty, with no unconsumed fragments;
   - `vX.Y.Z` does not exist and is greater than the latest tag;
   - `check-repo.py`, every `scripts/test-*.py` (render parity
     [#126](https://github.com/mw-ding/eng-crew/issues/126) included),
     markdownlint and the offline link check pass.
5. **Build** (same job). Build `eng-crew-X.Y.Z.tar.gz` and `SHA256SUMS`
   ([packaging](deliverables.md#packaging)); upload them as a workflow
   artifact with the release notes, which are the `[X.Y.Z]` section.
6. **Approval check.** The publish job verifies the owner's merge-ok marker
   at the merged cut PR's head and that the push actor matches the
   `RELEASE_OWNER` repository variable. Missing approval or an actor mismatch
   refuses publishing. There is no second owner approval after landing.
7. **Publish job** (`contents: write`). In the same workflow run, after
   validation and the approval check, create the annotated tag `vX.Y.Z` on
   the validated merge commit; create the GitHub Release with the notes and
   attach the bundle and `SHA256SUMS`. A tag created with the workflow token
   starts no other workflow, so validation, tagging and publishing stay in
   one run.
8. **Notice.** The publish job posts the release link on the release issue
   linked by the cut PR and closes it. No coordinator run watch is required.

`workflow_dispatch` on `main` with `version=X.Y.Z` and `dry_run` remains
for dry runs and manual fallback. `dry_run=true` validates and builds only;
it never tags or publishes. Other PRs touching the workflow or release
scripts run validate and build on a simulated cut without publishing.
A real fallback is owner-only and retains the
cut PR's per-PR merge-ok and actor check; it supplies no new approval path.

## Release gate

Summary of the registry row that [R1.3](#follow-up-issues) added; the
[gate registry](protocol.md#gate-registry) holds the current wording. It
gates publishing, not merging; the §7 gates are unchanged.

| Gate | Satisfied by | Who / how fast | Fail-open | Binding |
|---|---|---|---|---|
| Release approval | The owner's per-PR `pass=steer cmd=merge-ok sha=<head>` marker at the cut PR's head, verified by the publish job on the merged PR, with validation green and the push actor matching `RELEASE_OWNER` | Owner on the cut PR before landing, on the coordinator's ask under the §6 owner SLA; publish job verifies before tagging | None for publishing: no standing grant or auto-applied default publishes a release. The §6 owner-decision path may only defer or cancel it | backend (GitHub release workflow) |

**Enforcement gap.** This repo is private on the GitHub Free plan, which
cannot add required reviewers to an environment, and the bots share the
owner-level account on some runtimes
([merge enforcement](merge-enforcement.md), [#80](https://github.com/mw-ding/eng-crew/issues/80)).
The publish job checks the cut PR's head-bound owner merge-ok marker and
`RELEASE_OWNER` actor before tagging or publishing; environment approval is
not the release go. With `RELEASE_OWNER` unset, publishing refuses. Shared
owner-level accounts mean the actor check alone cannot distinguish a bot
from the owner, so owner authorization remains a convention enforced through
the marker: no role invents an owner merge-ok. The standing grant and an
auto-applied default never authorize publishing. Roles may dispatch dry runs;
only the owner dispatches a real manual fallback with the same approval.

## Rollback

| Case | Action |
|---|---|
| Validate or build fails | Nothing was published. Fix forward by PR; retry through the owner-only manual fallback |
| Published release is bad | Never delete or move a tag; pins depend on it. Edit the Release title to "Withdrawn" with a pointer, then cut a patch that reverts or fixes |
| An environment must go back | Reinstall the previous tag ([update path](#update-path)), re-render, drift check, deploy, record the version |
| A pack must go back | Move `eng_crew_version` back to the previous tag ([version pin](packs.md#version-pin)) |

## Update path

How installed environments learn about and take a new version. Pull only:
nothing pushes a version into an environment.

| Step | Mechanism | Owner |
|---|---|---|
| Record | The install writes the bundle's `VERSION` (a tag) next to the live copy | Bootstrap ([#144](https://github.com/mw-ding/eng-crew/issues/144)) |
| Learn | Each coordinator compares its recorded version with the latest GitHub Release in its triage window; bootstrap's `crew doctor` reports it too ([#160](https://github.com/mw-ding/eng-crew/issues/160) row 17). The live Grok Bot coordinator learns the same way; the publish job's release-issue notice is a courtesy, not the mechanism | Coordinator |
| Decide | Minor or patch: the coordinator upgrades. Major: the owner OKs it after reading the `**Breaking:**` entries | Coordinator / owner |
| Take | Fetch the bundle at the tag, check `SHA256SUMS`, re-render with the project profile, run `check-skill-drift.py --project` against the live dir, deploy, record `VERSION`. Grok Bot keeps the [mirror hold gate](runtimes/grok-bot.md#mirror-hold-gate) record for the deploy | Coordinator via bootstrap upgrade |
| Before bootstrap | Check out the tag in an eng-crew clone, or extract the release bundle ([README: Install](../README.md#install)), and run the same render, drift check and deploy by hand | Coordinator |

## Upstreaming the session tooling

The first non-Grok session built its helpers outside the repo, unversioned
([#144](https://github.com/mw-ding/eng-crew/issues/144) problem list). Each
becomes a deliverable `crew` subcommand, a module after
[#224](https://github.com/mw-ding/eng-crew/issues/224), so they land after
that split and touch no shared lines.

| Helper role | What it does | Becomes |
|---|---|---|
| Brief generator | Fills the [worker brief template](roles.md#worker-brief-template) from an issue, role, tier and engine | `crew brief` |
| Review runner | Runs the review pass, then the validate pass in a fresh session, on an engine different from the actual builder engine | `crew review` |
| Verdict poster | Posts the verdict post with review and validate sections and the `pass=verdict` marker on the full head SHA | `crew verdict` |
| Ack poster | Posts `pass=ack` and steering acks | `crew ack` |
| Merge-up runner | Merges the default branch into a behind change and posts the merge-up note | `crew merge-up` |
| Light re-check | The §6 merge-up re-approve: one light pass at the new head after an approval | `crew recheck` |

Proposed as follow-ups (below); the coordinator files them.

## Follow-up issues

| ID | Issue | Scope | Depends on |
|---|---|---|---|
| R1.2 | [#217](https://github.com/mw-ding/eng-crew/issues/217) | `scripts/changelog-cut.py`: `[Unreleased]` to `[x.y.z] - <date>` | this design |
| R1.3 | [#218](https://github.com/mw-ding/eng-crew/issues/218) | `release.yml`, validate and publish jobs, dry-run in CI, release gate row; `crew:sensitive` | R1.2 |
| R1.4 | [#219](https://github.com/mw-ding/eng-crew/issues/219) | Retro-tag `v1.0.0`; cut `v2.0.0` after M14 and the #139 smoke | R1.3, #139 |
| proposed | not filed yet | Deliverables manifest with an unclassified-path check; bundle build; helper upstreaming | listed in the #145 PR |
