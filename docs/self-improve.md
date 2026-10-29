# Self-improve intake

Failures and near-misses die in chat and PR threads unless something turns them
into work. This doc is the intake protocol: a cheap path from a failed or stuck
crew PR to a reviewable harness improvement. It is the `M11` answer to the
self-improve gap in the [spec](specs/framework.md).

Three artifacts, three jobs:

- **Intake issue = queue.** A short candidate card in an eng-crew issue.
- **Lesson = memory.** A dated file in [docs/lessons/](lessons/README.md), with a
  one-liner in the [findings buffer](findings/README.md) until promoted.
- **PR = encoded fix.** A skill, protocol or template change that goes through
  the normal builder, reviewer-validator and synthesizer pipeline.

Chat and agent memory are not the store. The repo is.

**Hard rules.** Triage never edits a skill, protocol or template, and nothing
here merges anything: harness changes are never auto-merged. Only the
synthesizer merges, as everywhere else ([protocol, section
7](protocol.md#7-merge-gate-synthesizer)).

## Triggers

Intake runs on events and a schedule, not on someone remembering.

| Trigger | Fires when | v1 status |
|---|---|---|
| `weekly-sweep` | The weekly intake pass finds an open PR labelled `crew:blocked` or with no update for more than N days | **Live**: [recipe below](#weekly-sweep-recipe) |
| `reviewer-changes` | The reviewer-validator posts `REQUEST_CHANGES`, or a PR is reopened after an `APPROVE` | Follow-up, documented only |
| `ci-red-after-done` | CI goes red on a crew PR after the builder reported it ready | Follow-up, documented only |
| `tripwire` | A tripwire or metrics-regression issue is opened | Follow-up, documented only |

Follow-up recipes, each one line:

- `reviewer-changes`: the coordinator reads the hidden `crew:v1` marker with
  `verdict=changes` (or a reopen event after `verdict=pass`) and drafts a card
  with Trigger `reviewer-changes`; failure class is the top blocking finding.
- `ci-red-after-done`: when the stuck-PR sweeper's CI-failed row fires on a PR
  the builder already reported ready, draft a card with Trigger
  `ci-red-after-done`; failure class is the failing job name.
- `tripwire`: when an issue carrying a tripwire or metrics-regression label is
  opened, draft a card linking it as Source, with Trigger `tripwire`.

Each follow-up should reuse the card shape and the coordinator's accept or
close step; none needs a new store.

## Candidate card

The template is [templates/intake-candidate.md](../templates/intake-candidate.md).
Every card has:

| Field | Meaning |
|---|---|
| Source | Link to the PR or issue the failure came from |
| Trigger | One of the four triggers above |
| Failure class | A short slug; also the duplicate key |
| Proposed fix | One line, a hint for the builder |
| Scope | `repo:` or `crew:`, with a one-line reason (see [Scope](#scope-repo-vs-crew)) |
| Lesson, Findings entry | Links, or `none yet` while pending |
| Decision | `pending`, `accept (repo:)`, `accept (crew:)` or `close - <reason>` |

Cards are filed as issues in `<owner>/eng-crew`, titled
`intake: <failure class> on <owner>/<repo>#<n>`, so that one queue holds every
candidate whichever product it came from. Never paste logs, tokens, emails,
private chat quotes or real box paths into a card (spec R1); link the evidence.

## Accept or close

The coordinator owns the decision. It decides in its next
[triage window](protocol.md#6-duties-on-wake-all-roles), so a card does not wait
longer than one awake half-day.

- **Accept.** The coordinator sets Decision, confirms or changes Scope, writes
  the lesson (or has the builder write it in the fix PR) and relabels the issue
  as a normal `crew:ready` builder issue. For `repo:` it opens the issue in the
  product repo and links it. For `crew:` the issue stays in
  `<owner>/eng-crew`. From here it is an ordinary issue: builder, reviewer-validator,
  synthesizer.
- **Close.** The coordinator closes the issue with a reason: duplicate of
  `#N`, not a harness problem, one-off, or already fixed. A closed card is not
  deleted. If the failure is a repeated small smell, add or bump its entry in
  [docs/findings/buffer.md](findings/buffer.md) instead of writing a lesson, so
  the count can reach the batch threshold.

Triage does not edit skills, protocol or templates. Only an accepted issue,
built and reviewed as a PR, changes them.

## Lesson path

1. **Findings first.** Append or bump a one-liner in
   [docs/findings/buffer.md](findings/buffer.md) using the template in the
   [findings README](findings/README.md).
2. **Lesson when there is analysis.** Write
   `docs/lessons/YYYY-MM-DD-<slug>.md` in the
   [entry format](lessons/README.md#entry-format), add it to the lesson Index,
   and use the [correction hierarchy](lessons/README.md#correction-hierarchy)
   for the Fix field.
3. **Fix as a PR.** The accepted issue's PR encodes the fix and updates the
   lesson's Status and Linked issue/PR in the same PR.

A `repo:` lesson lives in the product repo; a `crew:` lesson lives here. A card
accepted without a lesson or findings entry is incomplete (see Risks).

## Scope: `repo:` vs `crew:`

Every card carries one tag.

- **`repo:`** is product-local: a flaky test, a webhook quirk, a build detail.
  The lesson and the fix go in **that product repo**.
- **`crew:`** generalizes: a merge-gate race, missing evidence, a role
  checklist gap. The lesson and the fix go in this repo
  (`<owner>/eng-crew`) and, where the live copy changes, the box skills
  `eng-pr-pipeline` and `eng-crew-roles` (mirrored under spec R4).

**Promotion rule.** Default to `repo:`. Promote to `crew:` when the same
failure class has hit at least two repos, or the failure is clearly not
product logic. The coordinator promotes at triage; the card says why.

**Cross-scope.** A failure that needs both a product fix and a harness fix
becomes **two** issues: the `repo:` one in the product repo and a second
`crew:` one in eng-crew. A product PR never also patches a skill or protocol
silently; that edit needs its own eng-crew issue and PR.

## Roles

- **Coordinator:** drafts or reviews cards, files them, and owns accept or
  close, Scope and promotion. Runs the weekly pass from the
  [stuck-PR sweeper](../templates/coordinator-stuck-pr-sweeper.md).
- **Builder:** builds accepted issues: `crew:` issues in eng-crew, `repo:`
  issues in the product repo.
- **Reviewer-validator:** unchanged. Aware that its `REQUEST_CHANGES` is a
  trigger; it posts nothing extra.
- **Synthesizer:** unchanged. Aware that harness PRs merge only through the
  normal gate, never by a triage step.

## Weekly sweep recipe

The `crew:blocked` label is not defined elsewhere in these docs. For intake it
means "a crew PR the owner or coordinator has parked as blocked"; a repo that
does not use it can pass another name with `--label`, and the stale-days rule
still applies.

```sh
gh pr list --repo <owner>/<repo> --state open --limit 200 \
  --json number,title,url,labels,updatedAt,isDraft > <tmp>/prs.json
python3 scripts/intake-sweep.py --repo <owner>/<repo> <tmp>/prs.json
```

The helper ([scripts README](../scripts/README.md#intake-sweep-weekly-stuck-pass))
prints a draft card for each open PR labelled `crew:blocked` or untouched for
more than `--stale-days` (default 7). Draft PRs are skipped: unfinished work is
not stuck. Scope defaults to `repo:`. It makes no network call, files nothing
and edits no skill. The coordinator then reviews the drafts, drops duplicates,
fills Proposed fix, confirms or promotes Scope, and files the keepers as
eng-crew issues. Nothing about this step is automatic beyond the printout.

## Risks

Called out, not all solved in v1.

- **Card spam and duplicates.** A weekly sweep re-prints the same stuck PR. The
  coordinator searches open and closed intake issues for the Source and Failure
  class before filing, and closes duplicates.
- **Mis-scoped cards.** `repo:` by default can hide a general failure; `crew:`
  by eagerness can pull product quirks into the harness. Promotion needs the
  two-repo or not-product-logic test.
- **Triage without a lesson.** An accepted card that ships a fix but no lesson
  or findings entry leaves no memory. Accept is incomplete until one exists.
- **Secrets in pasted failure text.** Logs can carry tokens or paths. Link, do
  not paste; the repo guard's secret scan is a backstop, not a substitute.
- **Heuristic only.** Triage is a checklist, not a classifier. The helper
  flags stuck PRs; it cannot tell why they are stuck.
