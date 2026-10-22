# Builder routine B2: per-PR watch

Owner: `<BuilderBot>`. One watch per PR. `ci-failed` and
`review-changes-requested` belong to B2. `pr-merged` and `pr-closed` are
terminal events shared with V2 ([README.md](README.md)). B1 is in
[builder-b1.md](builder-b1.md).

Created by `<BuilderBot>` right after its worker opens PR `<n>`.

## Trigger

```json
{
  "type": "github",
  "repo": "<owner>/<repo>",
  "pr": "<n>",
  "events": ["ci-failed", "review-changes-requested", "pr-merged", "pr-closed"]
}
```

`"<n>"` becomes the PR number as a JSON number when the watch is created.

## Prompt

```text
Builder watch for <owner>/<repo> PR #<n>. Guard first: re-read live state. Stop
on crew:hold or crew:escalated, a stale SHA, or an existing marker for this
pass at head. Take a claim file in <state-dir>/<owner>__<repo>/claims/ before
working.

ci-failed: ignore cancelled or superseded runs and runs for an older head. Fix
real failures on the branch with a worker, then post a "[<BuilderBot>/ci-fix]"
COMMENT review naming the engine, model and effort that actually wrote the
round (every engine that wrote commits in the round, e.g. both if the worker fell back mid-round), with every commit carrying
an "Engine: <engine> <model> <effort>" trailer and the note's crew:v1 marker
carrying engine=/model=/effort=. At most 3 CI-fix attempts per PR. The next failure adds
crew:escalated, posts an escalation COMMENT review (blockers, what was tried,
decision needed) and messages <CoordinatorBot>.

review-changes-requested from <reviewer-login> on a crew PR (builder marker
present, not crew:external): relaunch a worker on the same branch with the
findings, preferably on the same engine. If the review carries a steer marker
with cmd=rework, use the user's note; that is not a round. After the push post
"[<BuilderBot>/fix] round <k> @ <sha7>": each finding -> what changed ->
proof. The note names the engine, model and effort that actually wrote the
round (every engine that wrote commits in the round, e.g. both if the worker fell back mid-round), every commit carries the
Engine trailer, and the note's crew:v1 marker carries engine=/model=/effort=.
Merge-up conflicts handed over by <SynthesizerBot>: merge
<default-branch> in with a merge commit, resolve, push.

pr-merged or pr-closed: delete this PR's worktrees and build output. This
PR-scoped watch then deletes itself; do not try to delete it.

Never use --no-verify. Workers never post to GitHub. Never write a line that starts with the steering
prefix.
Result goes to: no one; escalations go to <CoordinatorBot>.
```
