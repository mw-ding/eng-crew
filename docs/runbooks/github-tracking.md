# GitHub tracking

Onboarding module for the target repo's GitHub tracking setup, split out of
the [onboarding runbook](../runbook-new-repo.md) under the M26 modular
organization principle
([#676](https://github.com/mw-ding/eng-crew/issues/676)). It holds the
runbook's Step 1, the `crew:*` label setup, between
[Step 0: write, validate and render the profile](../runbook-new-repo.md#step-0-write-validate-and-render-the-profile)
and
[Step 2: add the reviewer as a collaborator](../runbook-new-repo.md#step-2-add-the-reviewer-as-a-collaborator).
Milestones and the GitHub Project board are still in the runbook's
[Step 3: create Milestones and link a GitHub Project (v2)](../runbook-new-repo.md#step-3-create-milestones-and-link-a-github-project-v2).
The `<author-login>` identity is defined in the runbook's prerequisite
[Identities](../runbook-new-repo.md#identities) section.

## Step 1: create the `crew:*` labels

Ten labels. Labels are safe state because no listener fires on them
([architecture.md](../architecture.md#labels) says who sets and clears each;
[GitHub backend: Labels](../backends/github.md#labels) has the label mechanics). The
names, colors and descriptions below are the ones used on the framework repo.
The `crew:needs-md` description says "owner decision" instead of a person's initials.

Before creating labels, list the existing namespace and capture the output:

```bash
export GH_TOKEN=$(gh auth token --user <author-login>)
gh label list -R <owner>/<repo> --search crew: --json name,color,description
```

If it returns no labels, proceed. If it returns exactly the ten labels below,
with these colors and descriptions, and
`<state-dir>/<owner>__<repo>/wiring.md` exists, this is an existing crew install;
rerunning with `--force` is safe. Any other result (other `crew:*` names,
different colors or descriptions, or no wiring doc) is a namespace collision.
Stop: another automation may own it
([step 5](../runbook-new-repo.md#step-5-product-safety-checks)).

After that pre-check:

```bash
while IFS='|' read -r name color desc; do
  gh label create "$name" -R <owner>/<repo> --color "$color" --description "$desc" --force
done <<'EOF'
crew:ready|0E8A16|Released to the builder; issue may be assigned and built
crew:in-review|1D76DB|PR open, awaiting CI + review/validation
crew:changes|D93F0B|Reviewer requested changes; builder fix round due
crew:approved|5319E7|Reviewer approved at head; synthesizer may merge
crew:escalated|B60205|Round/CI-fix cap hit or escalated; bots no-op until /crew resume
crew:hold|FBCA04|Paused: every bot no-ops on this item
crew:external|C5DEF5|External/fork PR: sandboxed validation, no tokens
crew:spec|0052CC|Spec PR: review pass only, merges on /crew merge-ok
crew:needs-md|F9D0C4|Blocked on an owner decision (recommended default + deadline)
crew:needs-mirror|E99695|Protocol/template change: merge blocked until the box skill is mirrored
EOF
```

`--force` updates the color and description if the label already exists, so the
command is safe to rerun only after the pre-check above. The same call through
the API, for one label:

```bash
gh api -X POST repos/<owner>/<repo>/labels \
  -f name='crew:ready' -f color='0E8A16' \
  -f description='Released to the builder; issue may be assigned and built'
```

Verify (capture this output):

```bash
gh label list -R <owner>/<repo> --search crew: --json name,color,description
```

Expect exactly ten rows, no extra `crew:*` label, and every color/description
as above.
