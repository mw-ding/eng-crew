# Release workflow and update path (design)

How a version of the [deliverables](deliverables.md) is cut, approved and
published, how installed environments take it, and how to roll back
(roadmap R1.1, [#145](https://github.com/mw-ding/eng-crew/issues/145);
umbrella [#110](https://github.com/mw-ding/eng-crew/issues/110);
[portable spec P9](specs/portable.md#2-requirements)).

This page adds no rule, gate, cap, marker field or label. It drafts the
release gate row that [R1.3](#follow-up-issues) adds to the
[gate registry](protocol.md#gate-registry) under the
[gate contract](protocol.md#gate-contract). Nothing here is implemented yet.

## Decisions

| Question | Choice | Alternatives considered |
|---|---|---|
| Trigger | Manual `workflow_dispatch` of `release.yml` on `main`, inputs `version` and `dry_run` | Milestone close: an outward action as a side effect of tracker hygiene, and not every milestone is a release. A release label: overloads `crew:*` state tags, which the protocol keeps for change state |
| Who dispatches | The coordinator at a milestone end, or the owner | Any role: a release is outward-facing, so it stays with the role that owns the queue |
| Who approves | The owner only, per release, through a protected `release` environment (owner decision; [#160](https://github.com/mw-ding/eng-crew/issues/160) row 9 guardrail) | A standing grant: none covers a release |
| CHANGELOG cut | A normal crew PR runs `scripts/changelog-cut.py <version>` ([#217](https://github.com/mw-ding/eng-crew/issues/217)) and lands through §7 before the dispatch | The workflow committing the cut to `main`: a direct push bypasses review and breaks invariant 4 (only the synthesizer lands). A workflow-opened PR: PRs opened with the workflow token start no CI, so §7 could never pass |
| What the workflow writes | Only a tag and a GitHub Release; never a commit | none |
| Release workflow PR | `crew:sensitive` ([#184](https://github.com/mw-ding/eng-crew/issues/184)); until that class lands, the owner's per-change merge-ok is stated on the PR | Standing doc-only merge-ok: never covers `.github/` |

## Steps

1. **Release issue.** The coordinator files "Release vX.Y.Z" with the bump
   reason: the largest change class among the `[Unreleased]` entries
   ([versioning](deliverables.md#versioning)).
2. **Cut PR.** A builder runs `changelog-cut.py X.Y.Z` on a branch; the diff
   is `CHANGELOG.md` only. It goes through review and the
   [§7 merge gate](protocol.md#7-merge-gate-synthesizer) like any change.
3. **Dispatch.** After the cut lands, the coordinator dispatches
   `release.yml` with `version=X.Y.Z` at `main` HEAD.
4. **Validate job** (read-only token). At the dispatched SHA it fails
   closed unless:
   - the top versioned `CHANGELOG.md` section is `[X.Y.Z]` and
     `[Unreleased]` above it is empty;
   - `vX.Y.Z` does not exist and is greater than the latest tag;
   - `check-repo.py`, every `scripts/test-*.py` (render parity
     [#126](https://github.com/mw-ding/eng-crew/issues/126) included),
     markdownlint and the offline link check pass.
5. **Build** (same job). Build `eng-crew-X.Y.Z.tar.gz` and `SHA256SUMS`
   ([packaging](deliverables.md#packaging)); upload them as a workflow
   artifact with the release notes, which are the `[X.Y.Z]` section.
6. **Approval.** The publish job needs the `release` environment. The run
   waits until the owner approves it. `dry_run=true` stops before this job;
   CI runs the validate and build steps in dry-run on every PR that touches
   the workflow or the release scripts.
7. **Publish job** (`contents: write`). Create the annotated tag `vX.Y.Z` on
   the validated SHA, not on `main` HEAD at approval time; create the GitHub
   Release with the notes; attach the bundle and `SHA256SUMS`.
8. **Notice.** The coordinator posts the release link on the release issue,
   closes it, and tells the owner in its owner channel.

## Release gate

Draft registry row, added by [R1.3](#follow-up-issues). It gates
publishing, not merging; the §7 gates are unchanged.

| Gate | Satisfied by | Who / how fast | Fail-open | Binding |
|---|---|---|---|---|
| Release approval | The owner's approval of the `release` environment deployment for the workflow run at the validated SHA, with the validate job green | Owner, on the coordinator's ask, under the §6 owner SLA | None for publishing: no merge-ok, standing grant or auto-applied default publishes a release. The §6 owner-decision path may only defer or cancel it | backend (GitHub environments) |

**Enforcement gap.** This repo is private on the GitHub Free plan, which
cannot add required reviewers to an environment, and the bots share the
owner-level account on some runtimes
([merge enforcement](merge-enforcement.md), [#80](https://github.com/mw-ding/eng-crew/issues/80)).
Until both gaps close, the approval is a convention, the same way
synthesizer-only merging is: no role ever approves a pending deployment or
dispatches with `dry_run=false`; the owner does both. The coordinator
dispatches only dry runs and asks.

## Rollback

| Case | Action |
|---|---|
| Validate or build fails | Nothing was published. Fix forward by PR; dispatch again |
| Published release is bad | Never delete or move a tag; pins depend on it. Edit the Release title to "Withdrawn" with a pointer, then cut a patch that reverts or fixes |
| An environment must go back | Reinstall the previous tag ([update path](#update-path)), re-render, drift check, deploy, record the version |
| A pack must go back | Move `eng_crew_version` back to the previous tag ([version pin](packs.md#version-pin)) |

## Update path

How installed environments learn about and take a new version. Pull only:
nothing pushes a version into an environment.

| Step | Mechanism | Owner |
|---|---|---|
| Record | The install writes the bundle's `VERSION` (a tag) next to the live copy | Bootstrap ([#144](https://github.com/mw-ding/eng-crew/issues/144)) |
| Learn | Each coordinator compares its recorded version with the latest GitHub Release in its triage window; bootstrap's `crew doctor` reports it too ([#160](https://github.com/mw-ding/eng-crew/issues/160) row 17). The live Grok Bot coordinator learns the same way; the releasing coordinator's notice is a courtesy, not the mechanism | Coordinator |
| Decide | Minor or patch: the coordinator upgrades. Major: the owner OKs it after reading the `**Breaking:**` entries | Coordinator / owner |
| Take | Fetch the bundle at the tag, check `SHA256SUMS`, re-render with the project profile, run `check-skill-drift.py --project` against the live dir, deploy, record `VERSION`. Grok Bot keeps the [mirror hold gate](runtimes/grok-bot.md#mirror-hold-gate) record for the deploy | Coordinator via bootstrap upgrade |
| Before bootstrap | Check out the tag in an eng-crew clone and run the same render, drift check and deploy by hand | Coordinator |

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
