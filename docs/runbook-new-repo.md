# Runbook: put the crew on a new repo

This runbook takes a repo from "no automation" to "one issue went through every
stage, merged, and closed out, with evidence". It ends with a verification
checklist. Do the steps in order and capture the evidence named in each step;
the [checklist](#verification-checklist) collects it.

The install path starts with `crew bootstrap`: write one `crew.toml`, preview
the install, then apply it ([Step 0](#step-0-write-validate-and-render-the-profile)).
The profile ([profile.md](profile.md)) replaces hand-filled placeholders.
The manual validate, resolve, render and state setup remain below as a fallback.
Then complete the GitHub install mechanics (Steps 1 to 4: labels, reviewer collaborator,
milestones and board, CI and protection;
[GitHub backend: Tracking](backends/github.md#tracking)), the product-safety
checks (Step 5), the state dir and routines from the rendered output (Steps 6
and 7), and a first test issue (Step 8).
For a local tmux crew instead of Grok Bot, see [tmux runtime](#tmux-runtime).

Read first: the [architecture overview](architecture.md), the
[stage protocol](protocol.md), and [roles, tiers and engines](roles.md). A
finished onboarding, with real values, is the
[agentconnect worked example](../examples/agentconnect/README.md).
This runbook onboards one repo. It does not change the protocol or the
templates; gaps found along the way go into [Known gaps](#known-gaps).

The `<name>` placeholder values used in every command are defined in
[Prerequisites: Command values](runbooks/prerequisites.md#command-values).

## Prerequisites

Moved to [Prerequisites](runbooks/prerequisites.md#prerequisites).

### Identities

Moved to [Prerequisites: Identities](runbooks/prerequisites.md#identities).

### Per-identity `gh` usage

Moved to
[Prerequisites: Per-identity `gh` usage](runbooks/prerequisites.md#per-identity-gh-usage).

### Token scopes

Moved to [Prerequisites: Token scopes](runbooks/prerequisites.md#token-scopes).

### Shared state dir

Moved to
[Prerequisites: Shared state dir](runbooks/prerequisites.md#shared-state-dir).

### Other prerequisites

Moved to
[Prerequisites: Other prerequisites](runbooks/prerequisites.md#other-prerequisites).

## Step 0: write, validate and render the profile

Both install paths live in [Profile install](runbooks/profile-install.md):

1. [Bootstrap (recommended)](runbooks/profile-install.md#bootstrap-recommended).
2. [Manual fallback](runbooks/profile-install.md#manual-fallback), when
   bootstrap is unavailable.

### Bootstrap (recommended)

Moved to
[Profile install: Bootstrap (recommended)](runbooks/profile-install.md#bootstrap-recommended).

### Manual fallback

Moved to
[Profile install: Manual fallback](runbooks/profile-install.md#manual-fallback).

## Step 1: create the `crew:*` labels

Moved to
[GitHub tracking: Step 1](runbooks/github-tracking.md#step-1-create-the-crew-labels).

## Step 2: add the reviewer as a collaborator

Moved to
[GitHub reviewer access: Step 2](runbooks/github-reviewer-access.md#step-2-add-the-reviewer-as-a-collaborator).

## Step 3: create Milestones and link a GitHub Project (v2)

Moved to
[GitHub tracking: Step 3](runbooks/github-tracking.md#step-3-create-milestones-and-link-a-github-project-v2).

## Step 4: check CI and branch protection

Moved to [GitHub CI and branch protection](runbooks/github-ci-protection.md):

1. [Step 4: CI discovery and current protection](runbooks/github-ci-protection.md#step-4-check-ci-and-branch-protection),
   items 1 to 4.
2. [Protection choice](runbooks/github-ci-protection.md#protection-choice),
   item 5.
3. [Merge settings and enforcement limits](runbooks/github-ci-protection.md#merge-settings-and-enforcement-limits),
   items 6 and 7.

## Step 5: product-safety checks

Moved to
[Product preflight: Automation, namespace and fork preflight](runbooks/product-preflight.md#automation-namespace-and-fork-preflight):
do these before installing any routine, since installing routines makes the
crew live, and write the answers in the wiring doc's section 0 ("Facts found
in the repo"); item 1, one automation system per repo; item 2, never touch the
product's own labels or commands; item 3, fork PRs and external contributors.
Items 4 to 8 moved to
[Product preflight: Workflow, repo-contract, toolchain and cutover checks](runbooks/product-preflight.md#workflow-repo-contract-toolchain-and-cutover-checks):
item 4, no workflow deletion that removes push CI on the default branch; item
5, repo rules that change the crew's wording; item 6, toolchain; item 7,
existing open PRs and issues; item 8, deploy secrets.

## Step 6: state dir and wiring doc

Moved to
[Grok Bot onboarding: Step 6](runbooks/grok-onboarding.md#step-6-state-dir-and-wiring-doc):
verify bootstrap's recorded install (`VERSION`, `install.json`, the state
listing) against the reviewed plan, keep bootstrap-owned files intact, copy
the deployed Grok Bot `wiring.md` if missing, then the manual-fallback state
setup, filling `wiring.md` from the deployed or rendered copy with
`planned`/`applied`/`live` status, `reviewer-engines.md` and the README seed.
The module also holds the worked example; its entry is
[Filled-in wiring.md](#filled-in-wiringmd-derived-from-the-template) below.

### Filled-in wiring.md (derived from the template)

Moved to
[Grok Bot onboarding: Filled-in wiring.md](runbooks/grok-onboarding.md#filled-in-wiringmd-derived-from-the-template):
the complete worked `wiring.md` after steps 1 to 6, with placeholders, the
pilot-observation qualification, the routine table, IDs and unsubscribed
events, and the note on template sections 3, 5, 6 and 7.

## Step 7: listener wiring per bot

Moved to
[Grok Bot onboarding: Step 7](runbooks/grok-onboarding.md#step-7-listener-wiring-per-bot):
the rendered or hand-filled routine origins, the Grok Bot
[cross-runtime limits](runtimes/grok-bot.md#cross-runtime-limits), the
merge-up rule with its re-approve, ack and normal-round distinctions and the
`pass=ack` exclusion, the five rules for all routines, the per-bot ownership
table and the creation-order table for one PR, then the
[per-routine details](runbooks/grok-onboarding.md#per-routine-details) for
B1 to A3 and recording each routine as it goes live. Its two child sections
keep their entries below.

### Steering wiring

Moved to
[Grok Bot onboarding: Steering wiring](runbooks/grok-onboarding.md#steering-wiring):
the single coordinator dispatcher (A2), the normal listeners that wake
owners, the `<user-logins>` allowlist and that bots never write a line that
starts with the steering prefix.

### Cutover for existing open PRs

Moved to
[Grok Bot onboarding: Cutover for existing open PRs](runbooks/grok-onboarding.md#cutover-for-existing-open-prs):
the one-pass backfill, `cutover` markers, labels and dependency-order kicks,
no PR body edits, and the cutover exemption from the builder `pass=watch`
merge gate, when it ends and the synthesizer hold and ping after it.

## Step 8: first test issue

Use a trivial, low-risk issue that touches only docs, so a failure costs
nothing. It should be small enough for the trivial tier ([roles.md](roles.md#tiers))
and should exercise every stage once.

### Template issue

Title: `crew smoke test: add docs/crew-smoke-test.md`

```markdown
## Goal

Prove the crew pipeline end to end on this repo with a docs-only change.

## Acceptance criteria

1. `docs/crew-smoke-test.md` exists and contains a heading and one sentence
   saying what it is.
2. The repo's required checks are green on the PR head.
3. The PR body has `## Acceptance Evidence` with one row per criterion.
4. Nothing outside `docs/crew-smoke-test.md` changes.

## Out of scope

Any product code. Any workflow, label or setting change.

## Role / tier hint

eng-backend (docs-only), trivial tier.

Part of #<parent>
```

Create it, label it `crew:ready`, then assign it to `<author-login>` (the
assignment is the event). Both can be done as the coordinator:

```bash
GH_TOKEN=$(gh auth token --user <author-login>) \
  gh issue create -R <owner>/<repo> --title "crew smoke test: add docs/crew-smoke-test.md" \
  --body-file smoke-issue.md --label crew:ready
GH_TOKEN=$(gh auth token --user <author-login>) \
  gh issue edit <n> -R <owner>/<repo> --add-assignee <author-login>
```

Assign it to the current open `M*` milestone and add it to the Project as Todo.
If the repo forbids closing keywords, the PR will say `Refs #<n>` and the coordinator closes the issue
after merge; note which applies.

### Expected event and marker sequence

Capture the timestamp and the evidence for every row; the checklist references
this table. Bot output is always a review body, never a plain comment.

| # | Stage | Event / trigger | Who acts | Expected GitHub state and markers |
|---|---|---|---|---|
| 1 | Spec and handoff | Issue created; `crew:ready` added | `<CoordinatorBot>` | Issue with numbered criteria. No wake: labels fire nothing |
| 2 | Handoff | `issue-assigned` | B1 wakes `<BuilderBot>` | Claim file for the issue under `claims/`; the builder checked `crew:ready`, no existing PR or branch |
| 3 | Build | Worker runs, toolchain pinned, push | `<BuilderBot>` worker | Branch `<role>/<n>-<slug>`; worker never posts to GitHub |
| 4 | PR | PR opened non-draft | `<BuilderBot>` | Body has `## Context` with `Closes #<n>` (or `Refs`), `## Changes Made`, `## Testing Done`, `## Test Output`, `## Acceptance Evidence`, `## Risks / Not Done`, and the line `<!-- crew:v1 role=builder issue=<n> tier=<tier> engine=<engine> model=<model> -->` before the signature. Label `crew:in-review`. Project item added. `pr-opened` fires |
| 5 | Intake | `pr-opened` | V1 wakes `<ReviewerBot>` | COMMENT review `[<ReviewerBot>/ack]`, marker `pass=ack`, as `<reviewer-login>`. V1 hands V2 creation to the `<ReviewerBot>` parent turn. B2 is not created at this step: `pr-opened` wakes only the reviewer |
| 6 | Steering no-op | `pr-comment` from the ack | A2 wakes `<CoordinatorBot>` | Ends at once, posts nothing. One expected extra wake per bot post |
| 7 | CI | Checks settle | GitHub Actions | `ci-passed` wakes V2. A `ci-failed` instead wakes B2: `[<BuilderBot>/ci-fix]` COMMENT review, at most 3 attempts |
| 8 | Review and validation | `ci-passed` | V2 wakes `<ReviewerBot>` | Review engine differs from the builder engine. Claim file `reviewer-validator-pr<n>-<sha7>` taken and deleted. Separate review and validation workers in unique worktrees |
| 9 | Verdict | Formal review at head | `<ReviewerBot>` as `<reviewer-login>` | One review per head SHA. `[<ReviewerBot>/verdict] round 1`, review and validation sections each with a marker, final line `<!-- crew:v1 role=reviewer-validator pass=verdict pr=<n> sha=<head-sha> round=1 verdict=pass -->`. In one step: `crew:approved` set, `crew:in-review` removed |
| 9a | Iterate (if changes) | `review-changes-requested` | B2 wakes `<BuilderBot>` | `verdict=changes`, `crew:changes`. Builder pushes and posts `[<BuilderBot>/fix] round 1 @ <sha7>`. CI, then a round-2 verdict. A third `REQUEST_CHANGES` escalates |
| 10 | Merge | `review-approved` | S1 wakes `<SynthesizerBot>` | Gate re-checked at head. `locks/merge.lock` taken. `gh pr merge <n> --squash --match-head-commit <sha>`. `[<SynthesizerBot>/merge]` COMMENT review, marker `pass=merge`. Branch deleted if configured |
| 11 | Close-out | `pr-merged` | A1 (`<CoordinatorBot>`), B2 (`<BuilderBot>`), V2 (`<ReviewerBot>`) | Issue closed (by `Closes`, or by the coordinator for `Refs`). `crew:ready` removed from the issue, `crew:in-review` gone from the PR. Project item Done. Builder deleted its worktrees and build output. B2 and V2 deleted themselves |
| 12 | Default-branch CI | Push run on the merge commit | GitHub Actions | Green. A failure fires `ci-failed` on `<default-branch>` and A1 files a fix issue; it does not touch the branch |

The trivial issue is expected to be approved in round 1; one fix round is
acceptable and exercises the iterate path. If the run needs more than two
nudges from a person, stop and find out which listener missed (see the wake
timeline in the checklist).

### Optional steering smoke test

On the test PR before merge, as one of `<user-logins>`, post a comment whose
first line is the hold command (the `/crew` prefix plus `hold`; write it in the
PR comment box, never in a doc or script). Expect: `crew:hold` added and a
`[<CoordinatorBot>/steer] ack hold` COMMENT review with
`pass=steer cmd=hold cmd-id=<comment id>`. Repeat with the resume command and
expect the label removed and a `resume` marker. Do this only if the steering
dispatcher is live.

## Verification checklist

Do not tick an item without its evidence. Paste the output, ID, URL or marker
line into an evidence file for the repo (modelled on the pilot's evidence
file: result, links, a timeline table, then gaps found) and link it from the
wiring doc. Never paste a token; command output that contains one must be
redacted before it is saved.

Verify that the V2 and S1 prompts carry the
[merge-up rule](#step-7-listener-wiring-per-bot): no `pass=ack` passes the merge gate.

| # | Check | Evidence to capture | Passes when |
|---|---|---|---|
| P1 | Profile validates | Successful bootstrap output and the recorded profile, or manual `crew-config.py validate` and `resolve` output ([Step 0](#step-0-write-validate-and-render-the-profile)) | Exit 0; no `<...>` value in the profile or resolved values; the state dir holds the same `crew.toml` |
| P2 | Render clean | Bootstrap's render preview and successful apply output (tmux: also `crew up` deployment), or manual `crew-render.py` output with the written paths | Exit 0; render/deploy matches the reviewed plan, no `file:line: reason` line; any manual or hand-fill fallback recorded in the wiring doc |
| P3 | Parity (Grok Bot) | Output of `python3 scripts/test-render-parity.py` | Exit 0 with `OK`: rendered default-profile routines match the template text |
| 1 | Identities and scopes | `gh api user --jq .login` for each identity; the scopes header for each | Two different logins; `repo` on both; `project` present on the identity running Project operations (delegation recorded) |
| 2 | Labels | Output of `gh label list -R <owner>/<repo> --search crew: --json name,color,description` | Ten rows with the names, colors and descriptions from step 1 |
| 3 | Reviewer access | Output of the collaborator `permission` call; pending invitation count | `write` and `0` pending |
| 4 | Milestones + Project | Milestone list and issue assignments; `<project-number>` and URL; Status option names | M1, M2, … milestones used; closed `M*` frozen (no new issues, follow-ups in next `M*`); board linked to repo with Todo, In Progress, In Review, Done |
| 5 | CI facts | Workflow list with triggers; latest push run on `<default-branch>` (URL); check names on a green head | Required check names written in the wiring doc; push CI status stated |
| 6 | Branch protection and merge settings | Protection JSON or the 404; merge-settings output | Matches the level chosen in step 4 |
| 7 | Product safety | Hooks and labels listing; the written decision on other automation, product labels, E2E PRs, fork handling, workflow changes | Only one automation system owns the repo; no product label or command touched; no workflow deleted in a way that removes push CI |
| 8 | State dir | `ls -la` of the state dir and `claims/`; `locks/merge.lock` present | Writable by every bot account; `wiring.md` and `reviewer-engines.md` filled |
| 9 | Routines | For each of B1, V1, S1, A1, A2, A3: routine ID, name, trigger JSON as created; the wiring doc rows showing `live` with a date | Six standing routines; triggers match the templates; no `review-commented` subscription |
| 10 | Test issue | Issue URL; label list; assignment time; claim file name | `crew:ready` present at assignment; one builder wake |
| 11 | PR | PR URL; body sections present; the builder marker line; `crew:in-review` time | Non-draft; all sections; engine and model named are the ones actually used |
| 12 | Intake | `[<ReviewerBot>/ack]` review id and its marker line; the routine folder ids of the B2 and V2 watches | Ack is a COMMENT review as `<reviewer-login>`; both watches exist and were created by parent turns; the B2 marker file `<state-dir>/<owner>__<repo>/watches/pr-<n>.b2` and the builder `pass=watch` marker are present |
| 13 | CI at head | Check runs at the verdict head (names, conclusions) | Every required check green at head |
| 14 | Verdict | Review id; the `pass=verdict` marker line; review and validation marker lines; builder engine vs reviewer engine | One formal review per head SHA; reviewer engine differs from the builder engine; `round` is correct |
| 15 | Label hygiene | Labels after the verdict | `crew:approved` set, `crew:in-review` removed in the same step |
| 16 | Merge | Merge commit SHA; the `[<SynthesizerBot>/merge]` review id and marker; approval-to-merge time | Squash merge at the approved head SHA; merge gate re-checked; branch deleted |
| 17 | Close-out | Issue state and closing time; labels on issue and PR; Project item status; worktree removal; the B2 and V2 watches gone | Issue closed; `crew:ready` and `crew:in-review` cleared; item Done; both watches deleted themselves |
| 18 | Default-branch CI after merge | Push run URL for the merge commit | Green, or a filed fix issue |
| 19 | Comment discipline | The list of bot-authored items on the PR: reviews only | No plain PR comments or inline comments by bots; no line starting with the steering prefix in any bot text or commit message |
| 20 | PR body untouched | GraphQL `userContentEdits` for the PR body | No edits after creation |
| 21 | Wake timeline | The timeline table below, filled | Every stage woke exactly one consumer; extra wakes explained (ack and bot posts wake the dispatcher once each) |
| 22 | Steering (if live) | Ack review ids and `cmd-id` markers for the hold and resume smoke test | Ack posted once per command id; label toggled |
| 23 | Rollback rehearsed on paper | The rollback steps below, with the IDs from item 9 | Every routine ID needed to remove the crew is written down |

Check item 20 with:

```bash
gh api graphql -f query='
  query($owner: String!, $repo: String!, $number: Int!) {
    repository(owner: $owner, name: $repo) {
      pullRequest(number: $number) { userContentEdits(first: 5) { totalCount } }
    }
  }' -f owner=<owner> -f repo=<repo> -F number=<n>
```

### Evidence timeline

Fill one row per event, as the pilot did. Times in one timezone.

| # | Time | Stage | Event / trigger | Bot (identity) | Evidence |
|---|---|---|---|---|---|
| 1 | `<time>` | Handoff | `issue-assigned` | `<CoordinatorBot>` → B1 | claim file name |
| 2 | `<time>` | PR | PR opened, `crew:in-review` | `<BuilderBot>` (`<author-login>`) | PR URL, builder marker |
| 3 | `<time>` | Intake | `pr-opened` → V1 | `<ReviewerBot>` (`<reviewer-login>`) | ack review id |
| 4 | `<time>` | Watches | B2 and V2 created | parent turns | routine IDs |
| 5 | `<time>` | CI | checks green at `<sha7>` | GitHub Actions | check-run summary |
| 6 | `<time>` | Verdict | `ci-passed` → V2 | `<ReviewerBot>`, `<engine>` | review id, marker line |
| 7 | `<time>` | Merge | `review-approved` → S1 | `<SynthesizerBot>` (`<author-login>`) | merge SHA, merge review id |
| 8 | `<time>` | Close-out | `pr-merged` → A1, B2, V2 | `<CoordinatorBot>`, `<BuilderBot>` | issue closed, worktree removed |

Add one row per fix round, merge-up and nudge. List any gap found at the end
("Gaps found"), the way the pilot did, and turn each into an issue.

## tmux runtime

This section is now navigation: each heading below keeps its anchor and
links to its module. The current steps are in the
[tmux onboarding module](runbooks/tmux-onboarding.md), with the `crew` and
`CREW_PROJECT` conventions in its
[Command conventions](runbooks/tmux-onboarding.md#command-conventions); the
dated 2026-10-30 run is in the
[tmux onboarding history](runbooks/tmux-onboarding-history.md).

### tmux prerequisites

Moved to
[tmux onboarding: tmux prerequisites](runbooks/tmux-onboarding.md#tmux-prerequisites).

### Set up the target repo

Moved to
[tmux onboarding: Set up the target repo](runbooks/tmux-onboarding.md#set-up-the-target-repo).

### Run the crew

Moved to [tmux onboarding: Run the crew](runbooks/tmux-onboarding.md#run-the-crew).

### tmux troubleshooting

Moved to
[tmux onboarding: tmux troubleshooting](runbooks/tmux-onboarding.md#tmux-troubleshooting).

### End-to-end run (2026-10-30)

Moved to
[tmux onboarding history: End-to-end run (2026-10-30)](runbooks/tmux-onboarding-history.md#end-to-end-run-2026-10-30)
(history, not current instructions).

## Rollback and offboarding

Moved to
[Offboarding: Rollback and offboarding](runbooks/offboarding.md#rollback-and-offboarding).

## Known gaps

Open items found while writing this runbook. Each follow-up is tracked as an
eng-crew issue:

- The templates' own open items still apply
  ([../templates/README.md](../templates/README.md#open-items)).
- Creating and deleting routines is platform-specific and not scripted in this
  repo; this runbook names what to create, not the platform call.
  [#27](https://github.com/mw-ding/eng-crew/issues/27) tracks a scripted routine
  installer for a new repo.
- "Only the synthesizer merges" is convention while the bots share an account.
  This limitation is by design for now, with no follow-up issue.
- Evidence a verdict depends on should be committed on the PR branch, not on a
  side branch. A change that does not move the PR head wakes no one and needs a
  manual rereview steer (lesson of Oct 20, 2026). The protocol now covers this
  (see [evidence requirements](protocol.md#3-evidence-requirements)).
