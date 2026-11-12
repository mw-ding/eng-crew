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

<include:policy/coordinator/signing.md>

<include:policy/shared/report.md>

<include:policy/shared/landing-authority.md>

<include:policy/coordinator/secret-retrieval.md>

<include:policy/coordinator/owner-config.md>

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
