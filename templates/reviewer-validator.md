# Reviewer-validator routines: V1 and V2

Owner: `<ReviewerBot>`. One standing routine (V1) and one per-PR watch (V2).
The full V2 prompt is in [reviewer-v2-watch.md](reviewer-v2-watch.md); the
engine choice is in [reviewer-engines.md](reviewer-engines.md).

## V1: PR intake

### Trigger

```json
{
  "type": "github",
  "repo": "<owner>/<repo>",
  "events": ["pr-opened"]
}
```

No allowlist, so external (fork) PRs are covered too.

### Prompt

```text
Guard first: re-read live PR state. Ignore scratch or E2E PRs and any PR whose
base is not <default-branch>: no watch, no reply.

Otherwise post a "[<ReviewerBot>/ack]" COMMENT review as <reviewer-login>
(skip the ack on drafts) and hand off to the parent turn to create watch V2 for
the PR; a routine run cannot create routines. If the author is not
<author-login>, label the PR crew:external and tell <CoordinatorBot> if the
fork's workflows await manual approval.

Never post plain PR comments or inline comments. Never write a line that
starts with the steering prefix.
Result goes to: no one.
```

## V2: per-PR watch

Created by the parent turn after V1, one per PR.

### Trigger

```json
{
  "type": "github",
  "repo": "<owner>/<repo>",
  "pr": "<n>",
  "events": ["ci-passed", "review-requested", "pr-merged", "pr-closed"]
}
```

`"<n>"` becomes the PR number as a JSON number when the watch is created.

### Prompt

See [reviewer-v2-watch.md](reviewer-v2-watch.md). Copy the prompt block from
there into the watch.
