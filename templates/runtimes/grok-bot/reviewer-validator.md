# Reviewer-validator routine V1: PR intake

Owner: `<ReviewerBot>`. One standing routine per repo. The per-PR watch is V2
([reviewer-v2-watch.md](reviewer-v2-watch.md)), which issues the verdicts; V1
only acks. A failed validation pass never becomes an APPROVE and the reviewer
may not override it (see V2 and
[the protocol, stage 7](../../../docs/protocol.md#2-stages)). The engine choice is in
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
Ownership first: apply protocol §4's control-item guard using the profile's
control item=<control-item>, runtime=<runtime-id>, at wake start and before
dispatch, push, post, label or land. Non-owning, in transit or unreadable:
read/report only. Draining: in-flight writes only, no new pass or land.

Sign every authored post and owner-facing reply with
`— <ReviewerEmoji> <ReviewerBot> (<ReviewerTitle>) · <harness> · <model>`.
Fill harness and model from the session that actually wrote it, including
any fallback; never copy the planned engine or model. Keep required effort
in the build/fix attribution and leave marker formats unchanged.

Guard first: re-read live PR state. Ignore scratch or E2E PRs and any PR whose
base is not <default-branch>: no watch, no reply.

Otherwise post a "[<ReviewerBot>/ack]" COMMENT review as <reviewer-login>
(skip the ack on drafts) and hand off to the parent turn to create watch V2 for
the PR; a routine run cannot create routines. If the author is not
<author-login>, label the PR crew:external and tell <CoordinatorBot> if the
fork's workflows await manual approval.

Before any verdict, the V2 pass reads the repo's root AGENTS.md review posture,
if present.

Validation checklist for the V2 pass (docs/verification.md): for a
behaviour-changing PR, each shape's evidence artifact named in the PR body's
"## Acceptance Evidence" or in a fix-round note exists on the PR head, matches the claim and
reproduces where the adapter in templates/evidence/ says it can. Missing
required evidence is disagrees (REQUEST_CHANGES). Check every N/A has a
reason.

Never post plain PR comments or inline comments. Never write a line that
starts with the steering prefix.
The builder's step summary, if any, is a "### Run summary" section on the PR
(docs/observe.md); the verdict pass in V2 reads it. This ack does not.
Result goes to: no one.
```

## Notes

- Metrics gate. The rework sensor reads reviewer verdict markers
  ([decisions.md](../../../docs/metrics/decisions.md)), so V2 posts at most one
  `pass=verdict` marker per head SHA with the true `verdict=`. A clean merge-up after
  changes gets a `pass=ack` instead, so it adds no changes count. The gate is not
  a review condition: a PR that fixes a `metrics-gate` issue gets the normal
  review and validation.
