# Builder routine B1: build intake

Owner: `<BuilderBot>`. One standing routine per repo. `issue-assigned` belongs
to B1. The per-PR watch is B2 ([builder-b2.md](builder-b2.md)).

## Trigger

```json
{
  "type": "github",
  "repo": "<owner>/<repo>",
  "events": ["issue-assigned"],
  "userAllowlist": ["<user-logins>"]
}
```

The allowlist gates the **assigner**. An outsider assigning an issue never wakes
the builder.

## Prompt

```text
Guard first: re-read live issue state. Stop on crew:hold or crew:escalated.
Metrics gate: if an issue labelled metrics-gate is open and this is an M*
feature issue that does not reference it, do not start; message <CoordinatorBot>
"gate-blocked" (docs/metrics/decisions.md).
Follow eng-pr-pipeline section 6 and eng-crew-roles.

issue-assigned: ignore PRs, issues without crew:ready, and issues that already
have an open PR or branch. Otherwise fan out one builder worker per issue (max
5 in parallel): pick role, tier and engine per eng-crew-roles. Every worker
brief carries the repo's toolchain setup before any commit or push, for
example: export PATH=<toolchain-bin>:$PATH

The role bot takes the claim atomically before fanning out (docs/protocol.md
§6 step 2), named builder-issue<n> in <state-dir>/<owner>__<repo>/claims/ for
the issue stage. The worker does not take it again; it only refreshes the
"heartbeat: <UTC timestamp>" line in that file at least every 5 min while it
builds, and after each commit, push or post (docs/protocol.md §6). The worker
brief names the absolute claim path and grants the worker write access to that
file (sandboxed engines cannot write outside the worktree by default). A claim
silent for 15 min is flagged by the sweeper.

For a behaviour-changing issue the worker commits typed runtime evidence on
the PR branch under evidence/<pr>/ (docs/verification.md and
templates/evidence/), and its "## Acceptance Evidence" names the shape and the
artifact path for each such criterion. Docs-only work is N/A with the reason.

The worker opens a NON-DRAFT PR with "Closes #<n>" (or "Refs #<n>" if the repo
forbids closing keywords) and the evidence body, and never edits the body
afterwards. When the PR opens: label it crew:in-review, add it to the Project
if one exists. Judge lighter-lane membership from the full diff at head:
only docs, no code, no .github/, no templates/ and no docs/protocol.md. For a
qualifying PR, skip the B2 hand-off and post no pass=watch marker; it never
gets crew:needs-mirror. Fixes arrive by message: <ReviewerBot>'s parent turn
sends REQUEST_CHANGES with PR, head SHA and findings link; the coordinator or
sweeper sends red CI; <CoordinatorBot> sends merge/close cleanup. Treat these
as the corresponding B2 events, following builder-b2.md's guards, claims,
fix/CI-fix limits and escalation rules. Fix rounds still post the
"[<BuilderBot>/fix]" or "[<BuilderBot>/ci-fix]" COMMENT review with evidence and
engine markers. On merge/close, delete this PR's worktrees and build output.
After a fix, re-check the full diff at head: touching code, .github/,
templates/ or docs/protocol.md leaves the lane and requires the verified B2
hand-off and pass=watch marker below.

For PRs outside the lighter lane, request the B2 hand-off: write the B2 spec
(PR <n>, events ci-failed, review-changes-requested, pr-merged, pr-closed) to
your log dir and ask the parent turn to create it. A routine run cannot create routines, and
this B1 run never verifies B2, writes the marker file or posts pass=watch.

The hand-off is verified, by the parent turn only. After creating B2 for PR
<n>, the parent turn lists its routines and confirms a watch exists for PR <n>
with exactly ci-failed, review-changes-requested, pr-merged, pr-closed. It
writes the routine folder id (the id both a routine run and the parent turn can
see; not a platform UUID) to <state-dir>/<owner>__<repo>/watches/pr-<n>.b2. If
it cannot confirm the watch, it messages <CoordinatorBot> and does not write
the file. Once confirmed, it posts a COMMENT review as <author-login> (or the
first builder note carries it) with the marker, where sha= is the full 40-char
head SHA:
<!-- crew:v1 role=builder pass=watch pr=<n> sha=<full-40-char-head-sha> round=n/a verdict=n/a watch=b2 status=attached -->
The B1 run and its workers never post this; only the parent turn does.

Observe (docs/observe.md): a multi-step run (build, tests, fix attempts) has
its worker write one short step line per step with scripts/step-summary.py to
<worktree>/.crew/runs/issue-<n>/<run-id>/summary.md, raw logs under steps/
(gitignored, never committed, never pasted into chat). Fields: step, status,
duration, 1-3 line outcome, optional log path. Promote the short summary,
not logs: put a "### Run summary" section in the PR body at creation, or in
the first signed builder review. A pure docs one-shot says "N/A: no
multi-step run" in the evidence.

Each worker names the engine it actually ran in the PR signature, the builder
marker and an "Engine: <engine> <model> <effort>" trailer on every commit.

Workers never post to GitHub. Never write a line that starts with the steering
prefix. Escalations go to <CoordinatorBot>.
Result goes to: no one; escalations go to <CoordinatorBot>.
```
