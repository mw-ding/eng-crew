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
Follow eng-pr-pipeline section 6 and eng-crew-roles.

issue-assigned: ignore PRs, issues without crew:ready, and issues that already
have an open PR or branch. Otherwise fan out one builder worker per issue (max
5 in parallel): pick role, tier and engine per eng-crew-roles. Every worker
brief carries the repo's toolchain setup before any commit or push, for
example: export PATH=<toolchain-bin>:$PATH

The worker opens a NON-DRAFT PR with "Closes #<n>" (or "Refs #<n>" if the repo
forbids closing keywords) and the evidence body, and never edits the body
afterwards. When the PR opens: label it crew:in-review, add it to the Project
if one exists, and request the B2 hand-off: write the B2 spec (PR <n>, events
ci-failed, review-changes-requested, pr-merged, pr-closed) to your log dir and
ask the parent turn to create it. A routine run cannot create routines, and
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

Each worker names the engine it actually ran in the PR signature, the builder
marker and an "Engine: <engine> <model> <effort>" trailer on every commit.

Workers never post to GitHub. Never write a line that starts with the steering
prefix. Escalations go to <CoordinatorBot>.
Result goes to: no one; escalations go to <CoordinatorBot>.
```
