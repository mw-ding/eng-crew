# Onboarding prerequisites

Onboarding module for what must be true before the target repo's install
starts, split out of the [onboarding runbook](../runbook-new-repo.md) under the
M26 modular organization principle
([#676](https://github.com/mw-ding/eng-crew/issues/676)). It holds the opening
of the runbook's
[Prerequisites](../runbook-new-repo.md#prerequisites) and its
[Identities](#identities) and
[Per-identity `gh` usage](#per-identity-gh-usage) subsections, before
[Step 0: write, validate and render the profile](../runbook-new-repo.md#step-0-write-validate-and-render-the-profile).
The remaining prerequisites are still in the runbook:
[Token scopes](../runbook-new-repo.md#token-scopes),
[Shared state dir](../runbook-new-repo.md#shared-state-dir) and
[Other prerequisites](../runbook-new-repo.md#other-prerequisites).

## Prerequisites

Do not start until every item here is true. Record the evidence in the
checklist.

### Identities

The crew uses two GitHub accounts ([architecture.md](../architecture.md#identities)):

- **Author identity** `<author-login>`: used by the coordinator, builder and
  synthesizer. It pushes branches, opens PRs and merges.
- **Reviewer identity** `<reviewer-login>`: used by the reviewer-validator for
  formal `APPROVE` / `REQUEST_CHANGES` reviews, and by the coordinator for
  steering signals. GitHub refuses a verdict from the PR's own author, so this
  account must be a different one.

The author identity is normally the repo owner or an admin of the repo, because
steps 1, 3 and 4 need admin rights. Setup can also be done by any account that
has admin on the repo; it does not have to be one of the two crew identities.

### Per-identity `gh` usage

Several accounts are logged in to `gh` on the same box. Never switch the active
account (`gh auth switch`, `gh auth login`, `gh auth logout`). Select the
credential per command instead:

```bash
# act as the author identity
GH_TOKEN=$(gh auth token --user <author-login>) gh <command> ...

# act as the reviewer identity
GH_TOKEN=$(gh auth token --user <reviewer-login>) gh <command> ...
```

To run several commands as one identity in a shell, export it for that shell
only: `export GH_TOKEN=$(gh auth token --user <author-login>)`. Never print,
paste or commit a token value. Docs, wiring files, logs and evidence name the
mechanism only.

Check both identities exist on the box:

```bash
gh auth status
GH_TOKEN=$(gh auth token --user <author-login>) gh api user --jq .login
GH_TOKEN=$(gh auth token --user <reviewer-login>) gh api user --jq .login
```
