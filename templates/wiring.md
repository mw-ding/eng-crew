# `<owner>/<repo>` wiring: event-driven PR pipeline (template)

Copy to `<state-dir>/<owner>__<repo>/wiring.md` and fill in. Keep it as the one
place that lists what is installed for this repo. Protocol: the
`eng-pr-pipeline` skill. Roles and engines: the `eng-crew-roles` skill. Terms:
[../docs/architecture.md](../docs/architecture.md).

Repo: `<owner>/<repo>`, default branch `<default-branch>`. Drafted `<date>`.
Status of each item below: `<planned | applied | live>` with a date.

## 0. Facts found in the repo

Record before installing anything. Examples of what to check:

- Which identities author and review PRs; is `<reviewer-login>` a write
  collaborator so that its reviews are binding?
- Is the repo a fork? Do upstream syncs have to go through a PR?
- Does a scratch or E2E flow open PRs or issues here? If so, name how bots
  ignore them.
- CI: which workflows and aggregate check names run on `pull_request`, which
  on push to `<default-branch>`, and which events re-run them (for example PR
  title or body edits, or `ready_for_review`).
- Do conflicting PRs get no CI? Does a draft turned ready get no CI?
- Does the product use its own labels or comment commands here? Crew state
  uses only `crew:*` and never touches them.

## 1. Identities and shared state

| Bot | Role | `gh` identity |
|---|---|---|
| `<CoordinatorBot>` | Coordinator | `GH_TOKEN=$(gh auth token --user <author-login>)`; `<reviewer-login>` for steering signals |
| `<BuilderBot>` | Builder | `<author-login>` |
| `<ReviewerBot>` | Reviewer-validator | `<reviewer-login>` for all reviews |
| `<SynthesizerBot>` | Synthesizer | `<author-login>` |

Shared state: `<state-dir>/<owner>__<repo>/` with `claims/` (per-pass claim
files), `locks/merge.lock` (serial-merge flock), `reviewer-engines.md` and
`sweeper-state.json`.

Labels to create: `crew:ready`, `crew:in-review`, `crew:changes`,
`crew:approved`, `crew:escalated`, `crew:hold`, `crew:external`, `crew:spec`
(plus `crew:needs-md` if used).

## 2. Routines per bot

Every saved prompt is an intent and defers to the skills. Each starts with the
same guard: re-read live PR or issue state, and stop on `crew:hold`,
`crew:escalated`, a stale SHA, or an existing marker for this pass at head.
Bots never post PR conversation comments or inline comments.

| Routine | Bot | Trigger | Template |
|---|---|---|---|
| B1 build intake | `<BuilderBot>` | `issue-assigned`, allowlist `<user-logins>` | [builder.md](builder.md) |
| B2 per-PR watch | `<BuilderBot>` | PR-scoped: `ci-failed`, `review-changes-requested`, `pr-merged`, `pr-closed` | [builder.md](builder.md) |
| V1 PR intake | `<ReviewerBot>` | `pr-opened`, no allowlist | [reviewer-validator.md](reviewer-validator.md) |
| V2 per-PR watch | `<ReviewerBot>` | PR-scoped: `ci-passed`, `review-requested`, `pr-merged`, `pr-closed` | [reviewer-v2-watch.md](reviewer-v2-watch.md) |
| S1 merge on approval | `<SynthesizerBot>` | `review-approved`, no allowlist | [synthesizer.md](synthesizer.md) |
| A1 after merge | `<CoordinatorBot>` | `pr-merged`; `ci-failed` on `<default-branch>` | [coordinator-after-merge.md](coordinator-after-merge.md) |
| A2 steering dispatcher | `<CoordinatorBot>` | `pr-comment`, `inline-review-comment`, allowlist `<user-logins>` | [coordinator-steering-dispatcher.md](coordinator-steering-dispatcher.md) |
| A3 stuck-PR sweeper | `<CoordinatorBot>` | schedule | [coordinator-stuck-pr-sweeper.md](coordinator-stuck-pr-sweeper.md) |

Deliberately not subscribed: `review-commented` (where all bot narrative
lands), `pr-pushed`, `review-thread-*`. Only the dispatcher holds comment
events. A researcher role, if any, has no listeners.

### 2a. Steering wiring

Single dispatcher: `<CoordinatorBot>`. The allowlist gates the **PR author**, so
A2 fires for every comment on PRs authored by `<user-logins>`; the prompt checks
the **commenter**. Commands (spelled after the steering prefix):

| Subcommand | Owner | Dispatch signal | Owner wakes via |
|---|---|---|---|
| hold | Coordinator | add `crew:hold` | none |
| resume | Coordinator | remove hold and escalated, `resume` marker, re-emit the stage signal | reviewer, builder or synthesizer |
| rework: `<note>` | Builder | `<reviewer-login>` REQUEST_CHANGES, `steer cmd=rework` | B2 `review-changes-requested` |
| rereview | Reviewer | re-request `<reviewer-login>` | V2 `review-requested` |
| merge-ok | Synthesizer | `<reviewer-login>` APPROVE, `steer cmd=merge-ok sha=<head-sha>` | S1 `review-approved` |
| escalate | Coordinator | `crew:escalated` plus an escalation COMMENT review | none |

External PRs: A2 does not fire, because the author is not allowlisted. Add a
per-PR watch with the comment events plus `pr-merged` and `pr-closed` when one
needs steering. Issue comments wake no one; steer issues by assignment, labels
or chat.

## 3. How state passes

`issue-assigned` -> builder builds -> PR opened -> `pr-opened` -> reviewer acks
and watches -> CI -> `ci-passed` -> review and validation -> one formal review
per head SHA, then either:

- `review-changes-requested` -> builder fixes -> push -> CI -> `ci-passed` ->
  next round; or
- `review-approved` -> synthesizer gate and merge -> `pr-merged` -> builder
  cleans up, coordinator assigns the next issue; the synthesizer merges
  `<default-branch>` into conflicting PRs.

## 4. Enforcement steps (the user decides; all reversible)

Record each as done or not, with a date:

1. `<reviewer-login>` is a write collaborator.
2. `<default-branch>` protection: required checks, 1 approving review,
   administrators included, no force pushes or deletions.
3. Squash-only merges and delete-branch-on-merge.
4. "Only the synthesizer merges" stays convention while bots share an account.
   Real enforcement needs a separate identity for the synthesizer.

## 5. Cutover plan for open PRs

For PRs that exist before the listeners (no `pr-opened` ever fires for them):
install routines, then backfill per-PR watches in one pass, post a `cutover`
marker on each PR (resets round counting; it stands in for a missing issue
link), label them `crew:changes` or `crew:hold` as appropriate, and kick them
in dependency order. Do not edit PR bodies, since that re-runs some workflows.

## 6. Wake cost

Each wake is a full bot turn. Track estimates per path (clean, typical, worst
before escalation) and the extra cost of steering, so listener changes can be
weighed.

## 7. Open risks

Record unverified listener semantics, PR-body-edit reruns, bot-comment
discipline, steering trust, the draft-to-ready CI gap, silent conflict stalls,
shared identities, external PRs, product collisions and project scope.

## 8. Pilot findings

Dated entries. Examples of what belongs here:

- A routine run cannot create or delete routines; per-PR watches are handed to
  the parent turn. PR-scoped watches self-delete on terminal events.
- A bot COMMENT review fires `pr-comment`; the dispatcher no-ops it.
- Builder and fix workers must set the repo toolchain on `PATH` before pushing.
- Label hygiene: the reviewer removes `crew:in-review` when adding
  `crew:approved` or `crew:changes`.
- Issue-link rule: if the repo forbids closing keywords, `Refs #<n>` satisfies
  the merge gate and the coordinator closes the issue after merge.
