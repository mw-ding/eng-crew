# Onboarding proof

Onboarding module for the first end-to-end proof on a new repo, split out of
the [onboarding runbook](../runbook-new-repo.md) under the M26 modular
organization principle
([#676](https://github.com/mw-ding/eng-crew/issues/676)). It holds the
opening of the runbook's
[Step 8: first test issue](#step-8-first-test-issue) and its
[Template issue](#template-issue), with the creation, assignment and
placement instructions. The
[Expected event and marker sequence](../runbook-new-repo.md#expected-event-and-marker-sequence),
[Optional steering smoke test](../runbook-new-repo.md#optional-steering-smoke-test),
[Verification checklist](../runbook-new-repo.md#verification-checklist) and
[Evidence timeline](../runbook-new-repo.md#evidence-timeline) are still in
the runbook.

## Step 8: first test issue

Use a trivial, low-risk issue that touches only docs, so a failure costs
nothing. It should be small enough for the trivial tier ([roles.md](../roles.md#tiers))
and should exercise every stage once.

### Template issue

Title: `crew smoke test: add docs/crew-smoke-test.md`

```markdown
## Goal

Prove the crew pipeline end to end on this repo with a docs-only change.

## Acceptance criteria

1. `docs/crew-smoke-test.md` exists and contains a heading and one sentence
   saying what it is.
2. The repo's required checks are green on the PR head.
3. The PR body has `## Acceptance Evidence` with one row per criterion.
4. Nothing outside `docs/crew-smoke-test.md` changes.

## Out of scope

Any product code. Any workflow, label or setting change.

## Role / tier hint

eng-backend (docs-only), trivial tier.

Part of #<parent>
```

Create it, label it `crew:ready`, then assign it to `<author-login>` (the
assignment is the event). Both can be done as the coordinator:

```bash
GH_TOKEN=$(gh auth token --user <author-login>) \
  gh issue create -R <owner>/<repo> --title "crew smoke test: add docs/crew-smoke-test.md" \
  --body-file smoke-issue.md --label crew:ready
GH_TOKEN=$(gh auth token --user <author-login>) \
  gh issue edit <n> -R <owner>/<repo> --add-assignee <author-login>
```

Assign it to the current open `M*` milestone and add it to the Project as Todo.
If the repo forbids closing keywords, the PR will say `Refs #<n>` and the coordinator closes the issue
after merge; note which applies.
