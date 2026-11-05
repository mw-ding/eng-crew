# Onboarding proof

Onboarding module for the first end-to-end proof on a new repo, split out of
the [onboarding runbook](../runbook-new-repo.md) under the M26 modular
organization principle
([#676](https://github.com/mw-ding/eng-crew/issues/676)). It holds the
opening of the runbook's
[Step 8: first test issue](#step-8-first-test-issue) and its
[Template issue](#template-issue), with the creation, assignment and
placement instructions, then the
[Expected event and marker sequence](#expected-event-and-marker-sequence) and
the [Optional steering smoke test](#optional-steering-smoke-test). The
[Verification checklist](../runbook-new-repo.md#verification-checklist) and
[Evidence timeline](../runbook-new-repo.md#evidence-timeline) are still in
the runbook.

## Step 8: first test issue

Use a trivial, low-risk issue that touches only docs, so a failure costs
nothing. It should be small enough for the trivial tier ([roles.md](../roles.md#tiers))
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
