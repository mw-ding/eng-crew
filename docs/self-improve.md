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
| `owner-feedback` | The owner tells the coordinator that work is too slow, too costly or missed a bug | Coordinator intake: [recipe below](#owner-feedback-recipe) |
| `runtime-blocker` | A crew or runtime defect blocks or slows a coordinator's run, in any repo | Coordinator intake: [recipe below](#runtime-blocker-recipe) |

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
| Trigger | One of the six triggers above |
| Failure class | A short slug; also the duplicate key |
| Proposed fix | One line, a hint for the builder |
| Scope | `repo:` or `crew:`, with a one-line reason (see [Scope](#scope-repo-vs-crew)) |
| Lesson, Findings entry | Links, or `none yet` while pending |
| Decision | `pending`, `accept (repo:)`, `accept (crew:)` or `close - <reason>` |

Cards are filed as issues in `<owner>/eng-crew`, titled
`intake: <failure class> on <owner>/<repo>#<n>`, so that one queue holds every
candidate whichever product it came from. Never paste logs, tokens, emails,
private chat quotes or real box paths into a card (spec R1); link the evidence.

### Owner-feedback recipe

On an owner message in its chat, the coordinator drafts an intake card with
Trigger `owner-feedback`. The owner may also provide feedback on a linked
issue or PR and bring it to the coordinator in chat; this adds no comment
listener or steering command. Verify that the feedback came from the owner,
not a bot or another contributor.

Use exactly one Failure class per card:

| Class | Owner reports |
|---|---|
| `too-slow` | Delivery or review takes too long |
| `too-costly` | Engine runs or crew work cost too much |
| `missed-bug` | A defect escaped the crew's checks |

Link the affected issue or PR as Source, using the feedback's public link
when available; summarize private chat without quoting it. If the source or
class is unclear, the coordinator clarifies with the owner before filing.
Feedback covering multiple classes becomes one card per class. Search open
and closed intake issues for the same Source and Failure class before filing;
link an existing card instead of creating a duplicate.

File the card in the existing intake queue with Scope `repo:` by default and
Decision `pending`, then use the normal accept-or-close step. The card is an
input to the [flavor feedback loop](flavors.md#feedback-loop); filing or
accepting it never changes the project's flavor or merge permission. Flavor
suggestions and the owner's accept path remain separate follow-up work.

### Runtime-blocker recipe

When a crew defect blocks or slows its run, the coordinator reports it in the
same turn, without being asked ([#299](https://github.com/mw-ding/eng-crew/issues/299);
[always-on triage](triage.md#triggers-and-cadence) T7). Defects include a
spawn, restart or launch failure, a role window stuck on a sandbox or
permission prompt, a crew command error, a watcher or poll timeout, or the
owner asking for a report.

```sh
crew feedback --project <project>/crew.toml --class spawn-failure \
  --summary "<one line>" --window <window> --sign "<signature>"
```

The helper prefills Source, role, engine and launch args from the window's
run record. It redacts credentials (tokens, bearer values, URL credentials,
`key=value` secrets), emails and box paths (`<state-dir>`, `<worktree>`,
`<home>`, any other absolute path as `<path>`) and files the card in `<owner>/eng-crew` (or
`--repo`) with Scope `crew:` and Decision `pending`. When an open card
already has that Failure class, it adds the new evidence as a comment
instead. If it cannot list the open cards, it files nothing. Use
`--dry-run` to print the card without posting. The coordinator never edits
eng-crew itself; it carries on with a product-side workaround, if any. The
next triage sweep picks the card up.

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

## Knowledge routing

A learning goes to its most specific owner: the narrowest place whose readers
need it. If nothing a role reads needs to change, it is a lesson only (last
row). Otherwise read the table top to bottom and stop at the first row that
fits.

| The learning is about | Owner | How it lands |
|---|---|---|
| The owner's own choices, not crew rules: engine order, merge grant, hold-label behaviour | Owner preferences: the install's profile, `crew.toml` ([layers](profile.md#layers-and-precedence)) | The owner edits it, or the coordinator on the owner's OK; no eng-crew PR |
| One product repo: a build command, a flaky test, a convention | That repo's root `AGENTS.md` | `repo:` card and a PR in the product repo |
| One organization's tools, commands, URLs or policy | That org's pack, outside eng-crew ([direction rule](packs.md#direction-rule)) | A change in the pack's own repo; eng-crew never names it |
| The crew in general: a gate, a role duty, a template step ([promotion rule](#scope-repo-vs-crew)) | eng-crew harness | `crew:` card and a PR in eng-crew |
| Nothing to change yet: a one-off, an analysis with no fix, a smell below the batch threshold | Lesson only | A lesson or findings entry ([lesson path](#lesson-path)); no always-loaded file changes |

The coordinator routes each card in its accept-or-close step. A profile or
org-pack learning leaves eng-crew: the coordinator closes the card as
`close - routed to profile` or `close - routed to org pack` and tells the
owner. A learning that fits two rows becomes one item per owner, as in
cross-scope above.

## Always-loaded files

An always-loaded file is one a role reads at the start of every session or
brief: a product repo's root `AGENTS.md`, this repo's `AGENTS.md`, the box
skills `eng-pr-pipeline` and `eng-crew-roles` with their reviewed copies
([protocol](protocol.md) and [roles](roles.md)), and the role briefs and
routine prompts rendered from `templates/`. Every line in one taxes every
session, so:

- **Correct, don't add.** Any role may fix wrong text in one: a stale path or
  command, a broken link, a sentence that contradicts `main` or the product.
  A correction replaces or deletes text and needs no intake card. It still
  lands by PR, here under the [protocol freeze](protocol.md#protocol-freeze)
  and the [mirror rule](../CONTRIBUTING.md#two-copies-one-change). A builder
  corrects only inside its task's scope and reports the rest to the
  coordinator.
- **Add only through a card.** A learning becomes new text in one (a rule, a
  reminder, an example) only through an accepted intake card and its PR.
  Otherwise it takes its row in [Knowledge routing](#knowledge-routing). This
  governs learnings; owner-approved milestone issues follow their own ACs.
- **Prune before adding.** An addition first looks for text to cut: a
  duplicate, a rule a check now enforces (lesson status `encoded`), or detail
  that can move to a linked doc behind a one-line pointer.

## Roles

- **Coordinator:** drafts or reviews cards, files them, and owns accept or
  close, Scope, promotion and routing. Runs the weekly pass from the
  [stuck-PR sweeper](../templates/runtimes/grok-bot/coordinator-stuck-pr-sweeper.md).
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
