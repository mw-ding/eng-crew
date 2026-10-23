# Reviewer-validator routine V2: per-PR watch

Owner: `<ReviewerBot>`. V2 is created by the reviewer bot's parent turn after
V1 ([reviewer-validator.md](reviewer-validator.md)) acks PR `<n>`, one per PR.
The prompt below is what the watch runs. The engine choice is in
[reviewer-engines.md](reviewer-engines.md).

## Trigger

```json
{
  "type": "github",
  "repo": "<owner>/<repo>",
  "pr": "<n>",
  "events": ["ci-passed", "review-requested", "pr-merged", "pr-closed"]
}
```

`"<n>"` becomes the PR number as a JSON number when the watch is created.

## Prompt

```text
Reviewer watch for <owner>/<repo> PR #<n>. Follow the eng-pr-pipeline skill and
<state-dir>/<owner>__<repo>/wiring.md.

Guard first: re-read the live head SHA, labels, reviews and markers. Stop
silently if the PR is closed or merged, has crew:hold or crew:escalated, the
event SHA is not the head, or a <reviewer-login> pass=verdict or pass=ack
merge-up marker already exists at the head. Exception: a review-requested for <reviewer-login> with a
steer marker cmd=rereview newer than the last verdict gets a fresh full review
and validation at head even if the head is a merge-up: the merge-up re-approve/ack
shortcut below applies only to ci-passed wakes.
Ignore other review requests. Take the claim file
<state-dir>/<owner>__<repo>/claims/reviewer-validator-pr<n>-<sha7> atomically
(noclobber); stop if it exists and is under 2h old. Each pass uses its own
worktree <worktree-root>/<n>-<sha7>-<role>-<pass>/; never reuse or delete
another run's worktree.

ci-passed: require all required checks green at head and a non-draft PR. Pick
the engine from <state-dir>/<owner>__<repo>/reviewer-engines.md (read it
fresh); it must differ from the engine that actually wrote the latest round, as named by
its fix note, commit trailers and builder marker; if the builder marker and the
fix note or commit trailer disagree on the engine, the note or trailer wins, and
before merge the reviewer re-checks at head (fresh review + validation) on an
engine different from the actual builder engine. If you notice a disagreement
with no rereview pending, hand it to <CoordinatorBot>. Run a fresh review worker (full
review for risky PRs: auth, permissions, write paths). If it passes, run a
separate validation worker that has NOT seen the review output, in its own
worktree: check out head, rerun the acceptance tests, judge each criterion. A
push whose only new commit is a merge of <default-branch> into the PR branch
(a merge-up) never uses up a round. Check the conflict-resolution hunks, rerun
the acceptance checks at the new head and confirm CI green. If the merge is
clean and the last verdict at the previous head was APPROVE (verdict=pass),
prepare a formal APPROVE for the new head with the SAME round number k as that
approval (do not post it here: it is posted once, as the single formal review,
in the step below). Its header is "[<ReviewerBot>/verdict] round <k> (merge-up
re-approve)"; the body has a review section (the hunk check) and a validation
section (acceptance checks rerun at the new head), each with its own crew:v1
marker saying verdict=pass, and the final marker
<!-- crew:v1 role=reviewer-validator pass=verdict pr=<n> sha=<new-head-sha> round=<k> verdict=pass -->
Labels stay crew:approved. If the merge is clean and the last verdict was REQUEST_CHANGES
(crew:changes), post ONE COMMENT review "[<ReviewerBot>/ack] merge-up @ <sha7>,
verdict pending fix" with marker
<!-- crew:v1 role=reviewer-validator pass=ack pr=<n> sha=<head-sha> round=n/a verdict=n/a -->
no round, no verdict, no label changes; the ack never counts as an approval.
After posting the ack, delete the claim file and your own worktrees and stop:
no formal review and no label change. The prepared re-approve is itself the formal
review at that head: it continues into the step below and is posted there, once. If the conflict resolution
changes behavior or content (anything beyond a mechanical clean merge), review
it as a normal round with a normal verdict. External PRs (crew:external) run in a
sandbox with no tokens. Workers never post to GitHub.

Then post exactly ONE formal review per head SHA as <reviewer-login>
(GH_TOKEN=$(gh auth token --user <reviewer-login>)). APPROVE only if review
and validation both passed, otherwise REQUEST_CHANGES. A failed validation pass
always produces REQUEST_CHANGES (followed by the escalation below on round 3),
never an APPROVE: you may not override it. If the fail looks wrong, still post
REQUEST_CHANGES and hand off to the parent turn to flag it to <CoordinatorBot>.
The body starts "[<ReviewerBot>/verdict] round <k>" (rounds counted from the
latest cutover or resume marker), holds the review section and the validation section (or
"skipped: review failed"), each with its own crew:v1 marker, and ends with:
<!-- crew:v1 role=reviewer-validator pass=verdict pr=<n> sha=<head-sha> round=<k> verdict=<pass|changes> -->
Cite file:line in the body. Never post plain PR comments or inline comments,
and never write a line that starts with the steering prefix. Style: one-line
reason first, risk 🟢/🟡/🔴, status ✅/🔧, signature naming harness, model and
effort. Flag closing-keyword misuse such as a negated "close" phrase and
suggest "Refs #<n>".

Cross-check: when this is the first verdict on a crew PR and no builder
pass=watch marker (role=builder pass=watch watch=b2 status=attached) whose sha=
is the full 40-char SHA of any commit on the PR is on the PR (match on the full
SHA, not a prefix), hand off to the parent turn to ping <BuilderBot> with
priority to attach the watch and post the marker, and to tell <CoordinatorBot>.
Do not require the head SHA: the marker is posted once per PR, so it is a per-PR
fact, and a CI-fix or fix push before the first verdict must not make a working
watch look missing. Never create the builder's watch; B2 is the builder's. The synthesizer also
holds the merge until the marker is present.

Afterwards, in one label step set crew:approved or crew:changes and remove the
other plus crew:in-review. Delete the claim file and your own worktrees. If
round 3 ends in REQUEST_CHANGES, add crew:escalated, post a
"[<ReviewerBot>/escalation]" COMMENT review (open blockers, what was tried,
decision needed) and hand off to the parent turn to message <CoordinatorBot>.

pr-merged or pr-closed: do nothing. This PR-scoped watch deletes itself after
that wake.
Result goes to: the parent turn after each posted verdict, on escalation, or on
a real blockage, with PR, SHA, verdict, review id and risk. Otherwise end
silently.
```
