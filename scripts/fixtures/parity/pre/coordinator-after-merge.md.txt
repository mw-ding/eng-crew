# Coordinator routine: after merge

Owner: `<CoordinatorBot>`. One standing routine per repo, with two listeners in
one group.

## Trigger

```json
[
  {
    "type": "github",
    "repo": "<owner>/<repo>",
    "events": ["pr-merged"]
  },
  {
    "type": "github",
    "repo": "<owner>/<repo>",
    "events": ["ci-failed"],
    "ciBranch": "<default-branch>"
  }
]
```

Drop the second listener if `<default-branch>` has no push CI. If it does, keep
it: the coordinator files a fix issue instead of touching the branch.

## Prompt

```text
Ownership first: apply protocol §4's control-item guard using the profile's
control item=<control-item>, runtime=<runtime-id>, at wake start and before
dispatch, push, post, label or land. Non-owning, in transit or unreadable:
read/report only. Draining: in-flight writes only, no new pass or land.

Sign every authored post and owner-facing reply with
`— <CoordinatorEmoji> <CoordinatorBot> (<CoordinatorTitle>) · <harness> · <model>`.
Fill harness and model from the session that actually wrote it, including
any fallback; never copy the planned engine or model. Keep required effort
in the build/fix attribution and leave marker formats unchanged.

Landing authority: the synthesizer alone decides direct land or train, batch
membership, order, isolating a failed member, and closing or rebuilding a batch.
Decide by protocol §7 and the resolved profile, never per-project steering.
Record each decision and reason in the train or merge report.

Coordinator inputs are a closed list of recorded pass=steer markers:

- cmd=land routes an approved change; re-read it and every gate before choosing how to land.
- cmd=hold with hold-until-#N and cmd=hold-release record a hold or its release,
  with a reason; wait until released or the dependency lands.
- cmd=merge-ok records the owner's permission at head; cmd=mirror-deferral
  records the owner's scoped mirror decision; cmd=profile records the owner's
  landing policy through the resolved profile. None supplies a gate waiver
  beyond the protocol's explicit allowance.
- cmd=urgent expedites one change alone ahead of batching, at its recorded head,
  with every §7 gate still applying. Urgency means a release blocker, security
  fix, explicit owner request or stop-the-line incident; record the reason.
- cmd=stop-landing stops the whole project's line on a red default branch,
  CI provider outage or owner request; cmd=resume-landing releases only the
  stop named by stop-id. Read all outstanding stops immediately before every
  squash, including direct lands and each train member. No merge-ok, standing
  grant or urgent marker overrides an open stop.

Everything else from the coordinator is advisory; the synthesizer may ignore it.

Landing control: before the first stop, the coordinator writes
`<state-dir>/<owner>__<repo>/landing-control.json` containing {"issue": N}, where N
is the tracker issue holding the project's signed stop/resume comments. On tmux use
`$CREW_STATE/landing-control.json`. Keep this reference across restarts and issue
closure; never relocate or delete it to clear a stop. Post all project stops
and resumes there with role=coordinator pass=steer, cmd-id identifying the
stop and stop-id identifying the stop a resume releases. Stop/resume is
project-scoped, survives a moved head, and never resets verdict rounds.
Unreadable control state blocks landing. Before each land read that issue's live
comments, even if closed, and the candidate PR's reviews; any unmatched stop
blocks. The tmux train gate performs this check too.

Escalate urgency only for the criteria above. Record the steer and reason
before delivering its refs; never prescribe train membership, ordering,
isolation, closure or rebuilding.

Follow eng-pr-pipeline section 6 (coordinator on pr-merged) and wiring.md.

ci-failed on <default-branch>: find the failing run, commit and PR. Ignore
known-noise failures that an open issue already tracks. Otherwise, if no fix
is already in flight, open a crew:ready issue (run link, suspected PR, "Part
of #<parent>") assigned to <author-login>. Never push to <default-branch> or
revert without the user's OK.

pr-merged: only when the base is <default-branch>; skip scratch and E2E PRs.
Check off the issue, update the parent spec issue, find newly unblocked
crew:ready issues and assign them, respecting "Depends on" order and the
5-builder ceiling. Respect crew:hold. Metrics gate: while an issue labelled metrics-gate is open,
do not assign new M* feature issues (docs/metrics/decisions.md); when the
merged PR closes that issue, remove the crew:hold and hold-until-#<gate> notes
you added for it, then resume assigning. Do no coding. Remove crew:ready from the
closed issue. Never auto-close an umbrella issue.

Soft findings: if the merged PR's approving verdict carried 🟡 or deferred
non-blockers, open the crew:ready follow-up per protocol §6 "Soft-finding
follow-up" (template there) in the same awake window (PT), assign it to
<author-login> and kick the builder, unless the user parked softs for a named
cut (then hold until the cut ends). Respect the 5-builder ceiling and
crew:hold above.

Lane resume: when a lane PR merges, lift crew:hold on the next step's PRs, add
crew:changes, and hand off so the builder starts a fix round and the reviewer
creates its watch.

Notify the user on lane advance, a new red on <default-branch>, a drained
board, or a blockage. Otherwise end silently.
Result goes to: the user, only for those cases.
```

## Notes

- If the repo closes issues itself with `Closes #<n>`, the merge does it. If the
  repo forbids closing keywords, the PR uses `Refs #<n>` and this routine closes
  the issue after merge, unless it is an umbrella issue.
- Skip Project steps when the repo has no GitHub Project.
