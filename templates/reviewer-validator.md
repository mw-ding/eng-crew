# Reviewer-validator routine V1: PR intake

Owner: `<ReviewerBot>`. One standing routine per repo. The per-PR watch is V2
([reviewer-v2-watch.md](reviewer-v2-watch.md)), which issues the verdicts; V1
only acks. A failed validation pass never becomes an APPROVE and the reviewer
may not override it (see V2 and
[the protocol, stage 7](../docs/protocol.md#2-stages)). The engine choice is in
[reviewer-engines.md](reviewer-engines.md).

## Trigger

```json
{
  "type": "github",
  "repo": "<owner>/<repo>",
  "events": ["pr-opened"]
}
```

No allowlist, so external (fork) PRs are covered too.

## Prompt

```text
Guard first: re-read live PR state. Ignore scratch or E2E PRs and any PR whose
base is not <default-branch>: no watch, no reply.

Otherwise post a "[<ReviewerBot>/ack]" COMMENT review as <reviewer-login>
(skip the ack on drafts) and hand off to the parent turn to create watch V2 for
the PR; a routine run cannot create routines. If the author is not
<author-login>, label the PR crew:external and tell <CoordinatorBot> if the
fork's workflows await manual approval.

Validation checklist for the V2 pass (docs/verification.md): for a
behaviour-changing PR, each shape's evidence artifact named in the PR body's
"## Acceptance Evidence" exists on the PR head, matches the claim and
reproduces where the adapter in templates/evidence/ says it can. Missing
required evidence is disagrees (REQUEST_CHANGES). Check every N/A has a
reason.

Never post plain PR comments or inline comments. Never write a line that
starts with the steering prefix.
Result goes to: no one.
```
