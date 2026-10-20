# Builder routines: B1 and B2

Owner: `<BuilderBot>`. One standing routine (B1) and one per-PR watch (B2).
`issue-assigned` belongs to B1. `ci-failed` and `review-changes-requested`
belong to B2, so each event has exactly one consumer
([README.md](README.md)).

## B1: build intake

### Trigger

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

### Prompt

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
if one exists, and hand off to the parent turn to create watch B2 for it. A
routine run cannot create routines.

Workers never post to GitHub. Never write a line that starts with the steering
prefix. Escalations go to <CoordinatorBot>.
Result goes to: no one; escalations go to <CoordinatorBot>.
```

Fallback if the builder's turn cannot outlive its worker: add `pr-opened` with a
`userAllowlist` of `<author-login>` to B1 and create B2 on that wake. This costs
one extra wake per PR.

## B2: per-PR watch

Created by `<BuilderBot>` right after its worker opens PR `<n>`.

### Trigger

```json
{
  "type": "github",
  "repo": "<owner>/<repo>",
  "pr": "<n>",
  "events": ["ci-failed", "review-changes-requested", "pr-merged", "pr-closed"]
}
```

`"<n>"` becomes the PR number as a JSON number when the watch is created.

### Prompt

```text
Builder watch for <owner>/<repo> PR #<n>. Guard first: re-read live state. Stop
on crew:hold or crew:escalated, a stale SHA, or an existing marker for this
pass at head. Take a claim file in <state-dir>/<owner>__<repo>/claims/ before
working.

ci-failed: ignore cancelled or superseded runs and runs for an older head. Fix
real failures on the branch with a worker, then post a "[<BuilderBot>/ci-fix]"
COMMENT review. At most 3 CI-fix attempts per PR. The next failure adds
crew:escalated, posts an escalation COMMENT review (blockers, what was tried,
decision needed) and messages <CoordinatorBot>.

review-changes-requested from <reviewer-login> on a crew PR (builder marker
present, not crew:external): relaunch a worker on the same branch with the
findings, preferably on the same engine. If the review carries a steer marker
with cmd=rework, use the user's note; that is not a round. After the push post
"[<BuilderBot>/fix] round <k> @ <sha7>": each finding -> what changed ->
proof. Merge-up conflicts handed over by <SynthesizerBot>: merge
<default-branch> in with a merge commit, resolve, push.

pr-merged or pr-closed: delete this PR's worktrees and build output. This
PR-scoped watch then deletes itself; do not try to delete it.

Workers never post to GitHub. Never write a line that starts with the steering
prefix.
Result goes to: no one; escalations go to <CoordinatorBot>.
```
