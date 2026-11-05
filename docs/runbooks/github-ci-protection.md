# GitHub CI and branch protection

Onboarding module for reading the target repo's CI and branch protection,
split out of the [onboarding runbook](../runbook-new-repo.md) under the M26
modular organization principle
([#676](https://github.com/mw-ding/eng-crew/issues/676)). It holds the
runbook's Step 4 CI discovery and current protection inspection, items 1 to 4,
between
[Step 3: create Milestones and link a GitHub Project (v2)](../runbook-new-repo.md#step-3-create-milestones-and-link-a-github-project-v2)
and
[Step 5: product-safety checks](../runbook-new-repo.md#step-5-product-safety-checks).
Items 5 to 7, the protection choice, merge settings and enforcement limits,
are still in the runbook's
[Step 4](../runbook-new-repo.md#step-4-check-ci-and-branch-protection).
The `<author-login>` identity is defined in the runbook's prerequisite
[Identities](../runbook-new-repo.md#identities) section.

## Step 4: check CI and branch protection

The crew is driven by CI results (`ci-passed`, `ci-failed`) and gated on
required checks, so read what the repo has before wiring anything.

1. List the workflows and when they run:

   ```bash
   GH_TOKEN=$(gh auth token --user <author-login>) \
     gh api repos/<owner>/<repo>/actions/workflows --jq '.workflows[] | {name, path, state}'
   gh api repos/<owner>/<repo>/contents/.github/workflows --jq '.[].name'
   ```

   Open each workflow file and write down its `on:` triggers. For each,
   record whether it runs on `pull_request` (and which activity types: PR title
   or body edits and `ready_for_review` change what fires `ci-passed`), on push
   to `<default-branch>`, on a schedule, or only on `workflow_dispatch` or
   `workflow_call`.

2. Check **push CI on the default branch**. If a workflow runs on push to
   `<default-branch>`, the coordinator's after-merge routine must also listen
   for `ci-failed` with `ciBranch` set to `<default-branch>`
   ([coordinator-after-merge.md](../../templates/runtimes/grok-bot/coordinator-after-merge.md)). If
   none does, drop that listener, and consider adding push CI to the test
   workflow so a bad merge is noticed.

   ```bash
   gh run list -R <owner>/<repo> --branch <default-branch> --event push --limit 10 \
     --json workflowName,conclusion,headSha,createdAt
   ```

   A workflow that fails on every push for a reason that is not code (for
   example a release job with no credentials on a fork) would fire `ci-failed`
   on every merge. Record it as known noise with an issue, and fix it by making
   the job manual-only, not by deleting it
   ([Step 5](../runbook-new-repo.md#step-5-product-safety-checks)).

3. Find the required check names. Use the names of the checks on a green PR
   head, exactly as GitHub reports them:

   ```bash
   gh api repos/<owner>/<repo>/commits/<green-head-sha>/check-runs \
     --jq '.check_runs[] | {name, conclusion, app: .app.slug}'
   ```

   Prefer one aggregate check (a final job that depends on the others and still
   reports when suites are skipped) over listing matrix job names. If the
   workflow can skip, make sure the aggregate still reports.

4. Read the current protection and merge settings:

   ```bash
   gh api repos/<owner>/<repo>/branches/<default-branch>/protection
   gh api repos/<owner>/<repo>/rulesets
   gh api repos/<owner>/<repo> \
     --jq '{squash: .allow_squash_merge, merge: .allow_merge_commit, rebase: .allow_rebase_merge, delete_branch: .delete_branch_on_merge, auto_merge: .allow_auto_merge}'
   ```

   A 404 "Branch not protected" from the first call is the normal answer for an
   unprotected branch.
