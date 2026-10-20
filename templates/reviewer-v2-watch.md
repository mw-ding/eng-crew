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
event SHA is not the head, or a <reviewer-login> pass=verdict marker already
exists at the head. Exception: a review-requested for <reviewer-login> with a
steer marker cmd=rereview newer than the last verdict gets a fresh full review.
Ignore other review requests. Take the claim file
<state-dir>/<owner>__<repo>/claims/reviewer-validator-pr<n>-<sha7> atomically
(noclobber); stop if it exists and is under 2h old. Each pass uses its own
worktree <worktree-root>/<n>-<sha7>-<role>-<pass>/; never reuse or delete
another run's worktree.

ci-passed: require all required checks green at head and a non-draft PR. Pick
the engine from <state-dir>/<owner>__<repo>/reviewer-engines.md (read it
fresh); it must differ from the engine that wrote the latest round. Run a fresh review worker (full
review for risky PRs: auth, permissions, write paths). If it passes, run a
separate validation worker that has NOT seen the review output, in its own
worktree: check out head, rerun the acceptance tests, judge each criterion. A
push that only merges <default-branch> in is not a new round: check the
conflict-resolution hunks. If they are clean, post ONE COMMENT review
"[<ReviewerBot>/ack] merge-up @ <sha7>, verdict pending fix" (or "verdict
stands" if the last verdict was an approval) with marker
"crew:v1 ... pass=ack ... verdict=n/a", the round unchanged, and change no
labels. If the resolution changes behavior or content, review it as a normal
round. External PRs (crew:external) run in a
sandbox with no tokens. Workers never post to GitHub.

Then post exactly ONE formal review per head SHA as <reviewer-login>
(GH_TOKEN=$(gh auth token --user <reviewer-login>)). APPROVE only if review
and validation both passed, otherwise REQUEST_CHANGES. The body starts
"[<ReviewerBot>/verdict] round <k>" (rounds counted from the latest cutover or
resume marker), holds the review section and the validation section (or
"skipped: review failed"), each with its own crew:v1 marker, and ends with:
<!-- crew:v1 role=reviewer-validator pass=verdict pr=<n> sha=<head-sha> round=<k> verdict=<pass|changes> -->
Cite file:line in the body. Never post plain PR comments or inline comments,
and never write a line that starts with the steering prefix. Style: one-line
reason first, risk 🟢/🟡/🔴, status ✅/🔧, signature naming harness, model and
effort. Flag closing-keyword misuse such as a negated "close" phrase and
suggest "Refs #<n>".

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
