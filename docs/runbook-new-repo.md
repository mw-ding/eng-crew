# Runbook: put the crew on a new repo

This runbook takes a repo from "no automation" to "one issue went through every
stage, merged, and closed out, with evidence". It ends with a verification
checklist. Do the steps in order and capture the evidence named in each step;
the [checklist](#verification-checklist) collects it.

The install path is profile first: write one `crew.toml`, validate it, resolve
it and render from it ([Step 0](#step-0-write-validate-and-render-the-profile)).
The profile ([profile.md](profile.md)) replaces hand-filled placeholders. Then
the GitHub install mechanics (Steps 1 to 4: labels, reviewer collaborator,
milestones and board, CI and protection;
[GitHub backend: Tracking](backends/github.md#tracking)), the product-safety
checks (Step 5), the state dir and routines from the rendered output (Steps 6
and 7), and a first test issue (Step 8).

Read first: the [architecture overview](architecture.md), the
[stage protocol](protocol.md), and [roles, tiers and engines](roles.md). A
finished onboarding, with real values, is the
[agentconnect worked example](../examples/agentconnect/README.md).
This runbook onboards one repo. It does not change the protocol or the
templates; gaps found along the way go into [Known gaps](#known-gaps).

Every `<name>` in a command below is a value from your resolved profile
(`crew-config.py resolve` prints each key; `<owner>` is `repo.owner`,
`<author-login>` is `identities.builder.gh_user`, and so on, per the "Replaces"
column of [profile.md: Keys](profile.md#keys)), except the few that come from
the output of the step using them, such as `<invitation-id>` (Step 2),
`<project-number>` (Step 3) and `<n>` (an issue or PR number). In every
command, `<owner>/<repo>` is the target repo.

## Prerequisites

Do not start until every item here is true. Record the evidence in the
checklist.

### Identities

The crew uses two GitHub accounts ([architecture.md](architecture.md#identities)):

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

### Token scopes

| Identity | Needs | Used for |
|---|---|---|
| `<author-login>` | `repo`; `workflow` only if workers may push files under `.github/workflows/`; `project` for Projects v2 | Branches, PRs, labels, merge, Project items |
| `<reviewer-login>` | `repo`; `project` if it updates the Project | Reviews, labels, steering signals |
| Whoever runs steps 1, 3 and 4 | Admin on the repo; `project` for step 3 | Labels, collaborators, Project, branch protection |

With fine-grained tokens the equivalents are: contents, pull requests and
issues read/write, metadata read, actions read, administration write for the
setup account, and the Projects permission on the owner.

Check the scopes of a classic token (the header lists them):

```bash
GH_TOKEN=$(gh auth token --user <login>) gh api -i user | grep -i '^x-oauth-scopes'
```

If `project` is missing for an identity, there are two options. Pick one and
record it in the wiring doc:

1. Add the scope to that identity: `gh auth refresh -h github.com -s project`.
   It needs a person at a browser to approve the device code, and it refreshes
   whichever account is active in `gh`. Do not switch the box's active account
   for this; have the account owner run it where that account is already
   active, or use option 2.
2. Do all Project operations as whichever identity already has `project`.
   (In the pilot, project operations ran as the reviewer identity while the
   author token lacked the scope.)

A GitHub Project is required for every crew repo. Resolve missing scope or
delegate Project operations before completing onboarding; skipping is not an
onboarding option.

### Shared state dir

All bots on the box share one directory per repo:
`<state-dir>/<owner>__<repo>/`. Create it once ([step 6](#step-6-state-dir-and-wiring-doc)):

| Path | Holds |
|---|---|
| `claims/` | Per-pass claim files `<role>-pr<n>-<sha7>`, taken atomically, deleted after posting |
| `locks/merge.lock` | The synthesizer's serial-merge lock (`flock`) |
| `crew.toml` | The profile this install was rendered from ([Step 0](#step-0-write-validate-and-render-the-profile)) |
| `wiring.md` | The filled-in wiring doc for this repo |
| `reviewer-engines.md` | The reviewer's current engine choice |
| `sweeper-state.json` | The stuck-PR sweeper's dedup state |

It must be writable by every bot account on the box and must not live inside
any repo checkout. It holds no credentials.

### Other prerequisites

- The reviewer-validator can run a different engine from the builder
  ([roles.md](roles.md#reviewer-engine-selection)). Private repos allow only
  Claude Code or Codex.
- The repo's required toolchain is known (for example the Node version and
  `COREPACK_HOME`), so builder and fix workers can pin it before any commit or
  push ([step 5](#step-5-product-safety-checks) records it).
- A human owner is available to approve things bots cannot: accepting the
  invitation if the reviewer account is not scriptable, a missing token scope,
  and branch-protection choices.

## Step 0: write, validate and render the profile

Needs Python 3.11+ and a checkout of this repo (`<path-to-this-repo>`); run
the commands from its root; `crew.toml` below stands for the path to your
profile file. Usage of both scripts:
[scripts: Profile validator](../scripts/README.md#profile-validator) and
[Renderer](../scripts/README.md#renderer).

1. **Write `crew.toml`.** Copy [profiles/default.toml](../profiles/default.toml)
   (GitHub for every concern, Grok Bot runtime) and replace every `<...>`
   value: `repo.owner`, `repo.name`, `repo.default_branch`, the logins in
   `[identities]` from [Identities](#identities) (`owners` are the user's own
   logins; `reviewer.gh_user` must differ from the other three), the bot
   display names, `runtime.timezone`, and `[paths]` with the
   [shared state dir](#shared-state-dir), the worker worktree root and the
   [toolchain](#other-prerequisites) `PATH` entry. Keep the `[engines]` routing
   unless the owner chose otherwise. Every key is in
   [profile.md: Keys](profile.md#keys).

2. **Validate** the file on its own:

   ```bash
   python3 scripts/crew-config.py validate crew.toml
   ```

   Expect exit 0. Each problem prints as `file:key: reason`. A value still
   written as a placeholder passes validation, so also check
   `grep -n '<' crew.toml` prints nothing.

3. **Resolve** the layers (core defaults, the default profile, your file):

   ```bash
   python3 scripts/crew-config.py resolve --project crew.toml
   ```

   Expect `crew-config: OK` and one `key = value  # layer` line per key, with
   no `<...>` value left (a key you deleted falls back to the default profile's
   placeholder). Capture the output: it is the value list for every command
   below. Add `--org-profile <path>` only if an org pack applies
   ([Layers and precedence](profile.md#layers-and-precedence)).

4. **Render** the role briefs and runtime artifacts:

   ```bash
   python3 scripts/crew-render.py --project crew.toml --out <out-dir>
   ```

   `--inputs` defaults to the real input tree, `templates/` (the Grok Bot
   templates and `backends/github.toml`). Expect `crew-render: OK (<k> files)`
   and the written paths: the Grok Bot routines under `runtime/` (role briefs
   under `briefs/` only once the input tree has `core/`). On any problem it
   prints `file:line: reason` and writes nothing. The parity check
   `python3 scripts/test-render-parity.py` proves the rendered default profile
   equals the template text
   ([scripts: Renderer](../scripts/README.md#renderer)).

**Hand-fill fallback.** Without rendered routines (if the renderer cannot
run), copy each template under
`templates/runtimes/grok-bot/` ([templates](../templates/README.md)) and replace each install-time placeholder with its resolved value from item 3
([templates: Placeholders](../templates/README.md#placeholders)). Record in
the wiring doc which path was used.

## Step 1: create the `crew:*` labels

Ten labels. Labels are safe state because no listener fires on them
([architecture.md](architecture.md#labels) says who sets and clears each;
[GitHub backend: Labels](backends/github.md#labels) has the label mechanics). The
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
([step 5](#step-5-product-safety-checks)).

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

## Step 2: add the reviewer as a collaborator

The reviewer identity needs **write** access so its reviews are binding and
counted by branch protection. On a user-owned repo that is an invitation the
reviewer account must accept.

1. Invite, as the repo admin. The response carries the invitation id.

   ```bash
   GH_TOKEN=$(gh auth token --user <author-login>) \
     gh api -X PUT repos/<owner>/<repo>/collaborators/<reviewer-login> \
     -f permission=push --jq '{id, invitee: .invitee.login, permissions}'
   ```

   On an org repo where `<reviewer-login>` is already an org member, access is
   granted at once and the call returns no body; skip to the verify step.

2. Accept, as the reviewer identity.

   ```bash
   GH_TOKEN=$(gh auth token --user <reviewer-login>) \
     gh api user/repository_invitations --jq '.[] | {id, repo: .repository.full_name}'
   GH_TOKEN=$(gh auth token --user <reviewer-login>) \
     gh api -X PATCH user/repository_invitations/<invitation-id>
   ```

   If the reviewer account cannot be driven from the box, the invitation link
   in its email or notifications does the same thing; record how it was done.

3. Verify (capture this output):

   ```bash
   GH_TOKEN=$(gh auth token --user <author-login>) \
     gh api repos/<owner>/<repo>/collaborators/<reviewer-login>/permission \
     --jq '{user: .user.login, permission}'
   GH_TOKEN=$(gh auth token --user <author-login>) \
     gh api repos/<owner>/<repo>/invitations --jq 'length'
   ```

   Expect `permission` of `write` and no pending invitation (`0`).

Also confirm the author identity has push access to the repo (and, if the repo
is a fork, to its own branches; builders never push to someone else's fork).

## Step 3: create Milestones and link a GitHub Project (v2)

Every crew repo requires GitHub Milestones **M1, M2, …** and a GitHub Project
board ([GitHub backend: Milestones and board](backends/github.md#milestones-and-board)).
Create the current milestone before handoff and assign issues to the
appropriate open `M*`. A **closed milestone is frozen**: no new issues may be
added to it; follow-ups go to the next `M*`. Capture the milestone list and
issue assignments as onboarding evidence.

The coordinator keeps the board item status current: Todo for new issues,
In Progress while a PR is being built, In Review while it is under review,
Done after merge.

1. Check the scope first. `project` must be on the identity that will run the
   commands (see [Token scopes](#token-scopes)). If it is not, follow the
   missing-scope options there before completing this step. A symptom of a
   missing scope is a GraphQL error that names the `project` scope or the
   `read:project` scope.

2. Create it and link it to the repo:

   ```bash
   export GH_TOKEN=$(gh auth token --user <login-with-project-scope>)
   gh project create --owner <owner> --title "<repo> crew board" --format json
   gh project link <project-number> --owner <owner> --repo <repo>
   ```

   Note `number` from the JSON output; that is `<project-number>`.

3. Set the Status field to exactly four options: Todo, In Progress, In Review,
   Done. A new project has the built-in Status field with Todo, In Progress and
   Done; In Review has to be added. List the field:

   ```bash
   gh project field-list <project-number> --owner <owner> --format json
   ```

   If the Status field already shows all four options, you are done. Otherwise
   add the missing option in the Project's settings page (field "Status", add
   option "In Review"), or replace the option list through GraphQL while the
   project is still empty (replacing options on a project that has items can
   clear their status values):

   ```bash
   gh api graphql -f query='
     mutation($field: ID!) {
       updateProjectV2Field(input: {
         fieldId: $field,
         singleSelectOptions: [
           {name: "Todo",        color: GRAY,   description: ""},
           {name: "In Progress", color: YELLOW, description: ""},
           {name: "In Review",   color: PURPLE, description: ""},
           {name: "Done",        color: GREEN,  description: ""}
         ]
       }) { projectV2Field { ... on ProjectV2SingleSelectField { options { name } } } }
     }' -f field='<status-field-id>'
   ```

   `<status-field-id>` is the `id` of the Status field in the `field-list`
   output. If the mutation is rejected on your GitHub version, use the settings
   page.

4. Make sure the board's auto-add and status workflows do not conflict with the
   crew: the coordinator adds issues and the builder adds PRs by hand. A
   built-in "item closed" → Done workflow is fine.

5. Verify (capture this output):

   ```bash
   gh project view <project-number> --owner <owner> --format json --jq '{number, title, url}'
   gh project field-list <project-number> --owner <owner> --format json \
     --jq '.fields[] | select(.name=="Status") | .options[].name'
   gh api graphql -f query='query($o: String!, $r: String!) { repository(owner: $o, name: $r) { projectsV2(first: 10) { nodes { number title } } } }' \
     -f o=<owner> -f r=<repo>
   ```

   Expect four option names in order, and the project listed under the repo's
   linked projects.

Record `<project-number>` and the current `M*` milestone in the wiring doc.

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
   ([coordinator-after-merge.md](../templates/runtimes/grok-bot/coordinator-after-merge.md)). If
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
   ([Step 5](#step-5-product-safety-checks)).

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

5. Choose a protection level with the owner. All are reversible
   ([Rollback](#rollback-and-offboarding)); the crew works at every level.

   | Level | What it adds | Cost |
   |---|---|---|
   | A. Convention only | Nothing. The synthesizer checks the merge gate itself ([protocol.md](protocol.md#7-merge-gate-synthesizer)) | Anyone with write access, including a bot with the wrong token, can merge or push |
   | B. Required checks | Required status checks on `<default-branch>` | Merges blocked while checks are red or missing |
   | C. Checks plus 1 review (pilot) | B, plus one approving review, administrators included, no force pushes or deletions | Blocks the owner's own manual merges and direct pushes too, unless they go through the same gate or the setting is toggled |

   Apply level C (adjust the checks; drop what you did not choose):

   ```bash
   cat > protection.json <<'EOF'
   {
     "required_status_checks": {
       "strict": false,
       "checks": [ { "context": "<aggregate-check-name>", "app_id": 15368 } ]
     },
     "required_pull_request_reviews": {
       "required_approving_review_count": 1,
       "dismiss_stale_reviews": false,
       "require_code_owner_reviews": false,
       "require_last_push_approval": false
     },
     "enforce_admins": true,
     "restrictions": null,
     "allow_force_pushes": false,
     "allow_deletions": false
   }
   EOF
   GH_TOKEN=$(gh auth token --user <author-login>) \
     gh api -X PUT repos/<owner>/<repo>/branches/<default-branch>/protection --input protection.json
   rm protection.json
   ```

   `app_id` 15368 is GitHub Actions; use `-1` to accept the check from any
   source. Stale approvals stay valid on purpose: the synthesizer's SHA-bound
   marker check keeps approvals current, and turning on
   `dismiss_stale_reviews` makes every merge-up need a fresh approval.
   Before turning protection on, make sure no workflow pushes to
   `<default-branch>` (release jobs often do); the review gate would block it.

6. Squash-only merges and branch cleanup. Merge-ups by update-branch still
   create merge commits on PR branches; this setting only affects how a PR
   lands on `<default-branch>`:

   ```bash
   GH_TOKEN=$(gh auth token --user <author-login>) \
     gh api -X PATCH repos/<owner>/<repo> \
     -F allow_squash_merge=true -F allow_merge_commit=false \
     -F allow_rebase_merge=false -F delete_branch_on_merge=true
   ```

7. "Only the synthesizer merges" stays a **convention** while bots share an
   account. Real enforcement needs the synthesizer on its own identity (for
   example a GitHub App) in an org repo where merge restrictions can name it.
   Record that as a known gap, not a blocker.
   See [merge enforcement](merge-enforcement.md) for a ruleset alternative,
   squash-only merging and personal-repository limits.

Capture the outputs of items 1 to 6 for the checklist.

## Step 5: product-safety checks

Do these before installing any routine; installing routines is what makes the
crew live. The wiring doc's section 0 ("Facts found in the repo") is where the
answers go.

1. **One automation system per repo.** The protocol allows only one automation
   system to own a repo at a time ([protocol.md](protocol.md#8-safety)). Look for
   others and decide who owns what before continuing:

   ```bash
   gh api repos/<owner>/<repo>/hooks --jq '.[] | {name, events, active}'
   gh label list -R <owner>/<repo> --limit 200
   gh api repos/<owner>/<repo>/contents/.github --jq '.[].name'
   ```

   Look for webhooks, GitHub Apps, dependency bots, merge queues, auto-merge,
   other bots that react to labels or comments, and a product-side
   orchestrator. If any of them also assigns issues, opens PRs, reviews or
   merges, they must be switched off for the repo or scoped away from crew PRs
   before you continue. Write the decision into the wiring doc.

2. **Do not touch the product's own labels or commands.** The crew uses only
   `crew:*` labels and comment commands that begin with the steering prefix.
   If the product has its own labels, slash commands, PR completion contracts,
   or live E2E flows that open and close issues or PRs on the same repo, list
   them, and make sure no crew routine acts on them. A scratch or E2E PR still
   fires `pr-opened`; the reviewer's intake prompt must name how it ignores
   them (a title tag, a base-branch pattern). Never rename, delete or recolor
   a product label, even to "tidy up".

3. **Fork PRs and external contributors.** PRs from forks are untrusted
   ([protocol.md](protocol.md#8-safety)):
   - The reviewer intake routine has no allowlist, so it labels them
     `crew:external` and runs validation in an isolated sandbox with **no
     tokens**.
   - A first-time contributor's workflows may wait for a maintainer's "Approve
     and run" click; until then there is no CI and no `ci-passed`. The
     reviewer flags it to the coordinator, who tells the user.
   - The steering dispatcher's allowlist gates the PR **author**, so it does not
     fire on external PRs. A per-PR comment watch is added only when the user
     wants to steer one.
   - Builders never push to fork branches.
   - If the repo itself is a fork of an upstream, upstream syncs have to go
     through a PR when branch protection is on; the sync button and direct
     pushes will be blocked.
   - Check `Settings > Actions > General > Fork pull request workflows` so
     that fork PRs do not get repo secrets.

4. **No workflow deletion that removes push CI on the default branch** (pilot
   lesson, Oct 19, 2026). In the pilot, the test workflow was only called by a
   release workflow; deleting the failing release workflow would have removed
   the repo's only push CI on `<default-branch>`. The fix was to keep the
   release workflows but make them manual-only (`workflow_dispatch`), and to add
   a push trigger on `<default-branch>` to the test workflow. Before touching
   any workflow file:

   ```bash
   grep -rn -E 'workflow_call|workflow_dispatch|^on:|^  push:|^  pull_request:|uses: \./\.github/workflows' .github/workflows
   ```

   Work out which workflow actually runs tests on push to `<default-branch>`,
   and which workflows call which. Disable a noisy workflow by trigger change
   or `gh workflow disable`, never by deletion, unless something else provides
   the same push CI. After the change, push or merge once and confirm a push run
   appears (`gh run list --branch <default-branch> --event push`).

5. **Repo rules that change the crew's wording.** Read the repo's contributor
   docs (`CONTRIBUTING`, agent instructions, PR templates). If the repo forbids
   closing keywords in PR bodies, the builder writes `Refs #<n>`; that satisfies
   the merge gate, and the coordinator closes the issue after merge
   ([wiring.md pilot findings](../templates/runtimes/grok-bot/wiring.md#8-pilot-findings)). If it
   mandates a commit or PR-title convention (for example conventional titles),
   put it in every worker brief.

6. **Toolchain.** Find what hooks and CI need (pre-push hooks that need a
   particular runtime, package-manager caches that need a writable home). Record
   the `PATH` and environment setup as `<toolchain-bin>` (`paths.toolchain_bin`
   in `crew.toml`; re-run Step 0 if it changed); every build and fix worker
   brief sets it before any commit or push.

7. **Existing open PRs and issues.** `pr-opened` never fires for PRs that
   already exist, and issues need `crew:ready` plus assignment. Decide whether
   to run the cutover for each open PR
   ([cutover](#cutover-for-existing-open-prs)) or to leave them with their
   authors.

8. **Deploy secrets.** Record shared deploy secret names and consuming hosts
   in the wiring doc; add the
   [protocol §3 sync AC](protocol.md#3-evidence-requirements) to new deploy
   milestones/issues.

## Step 6: state dir and wiring doc

1. Create the state dir and files:

   ```bash
   mkdir -p <state-dir>/<owner>__<repo>/claims <state-dir>/<owner>__<repo>/locks
   : > <state-dir>/<owner>__<repo>/locks/merge.lock
   cp crew.toml <state-dir>/<owner>__<repo>/crew.toml
   cp <path-to-this-repo>/templates/runtimes/grok-bot/wiring.md <state-dir>/<owner>__<repo>/wiring.md
   cp <path-to-this-repo>/templates/runtimes/grok-bot/reviewer-engines.md <state-dir>/<owner>__<repo>/reviewer-engines.md
   ls -la <state-dir>/<owner>__<repo>/ <state-dir>/<owner>__<repo>/claims
   ```

2. Fill in `wiring.md` from [../templates/runtimes/grok-bot/wiring.md](../templates/runtimes/grok-bot/wiring.md):
   section 0 from steps 1 to 5 above, section 1 from the identities, section 2
   from [Step 7](#step-7-listener-wiring-per-bot), section 4 from the choices in
   step 4. Start from the rendered `<out-dir>/runtime/wiring.md` instead,
   with the profile values already in. Mark every item `planned`, then `applied` or `live` with a date as
   you go. Keep it the one place that lists what is installed.

3. Copy the template, `reviewer-engines.md`, and fill `Updated` plus the
   allowed engine set (private repos: Claude Code or Codex only). Only the
   reviewer bot's main chat edits it afterwards
   ([reviewer-engines.md](../templates/runtimes/grok-bot/reviewer-engines.md)).

4. Install the README seed. Copy [../templates/product-readme.md](../templates/product-readme.md)
   into the repo root `README.md` and fill every section, or verify the
   existing README already has problem, what it is, how to run / use, how the
   crew works and status. Record which in the wiring doc. A product repo
   without such a README fails [protocol safety](protocol.md#8-safety).

### Filled-in wiring.md (derived from the template)

This is what the doc looks like after steps 1 to 6, with placeholders still in
place for your values. A real, dated one is in
[../examples/agentconnect/wiring-summary.md](../examples/agentconnect/wiring-summary.md).

````markdown
# `<owner>/<repo>` wiring: event-driven PR pipeline

Repo: `<owner>/<repo>`, default branch `<default-branch>`. Drafted `<date>`.
Protocol: the `eng-pr-pipeline` skill. Roles and engines: `eng-crew-roles`.

## 0. Facts found in the repo

- Identities: PRs authored and merged as `<author-login>`; verdicts posted as
  `<reviewer-login>` (write collaborator since `<date>`, invitation accepted).
- Fork of an upstream: `<yes, syncs go through a PR | no>`.
- Product automation on this repo: `<its labels, commands, E2E flows, and how
  the reviewer intake ignores scratch PRs>`. Crew state uses only `crew:*`.
- CI: workflows `<names>`; on `pull_request` (`<activity types>`):
  `<aggregate check name>`; push CI on `<default-branch>`: `<yes: workflow,
  no>`; known noisy workflows: `<none | issue #n>`.
- Observed in Step 4 (pilot behavior is an example, not a repo default):
  conflicting PRs: `<CI runs | no CI (observed on the pilot)>`; draft turned
  ready: `<CI and wake | no CI, no wake (observed on the pilot): builders open
  non-draft PRs only>`.
- Repo rules: closing keywords `<allowed | forbidden: use Refs #n>`;
  title convention `<convention>`; toolchain `<toolchain-bin>`.
- Token scopes: `<author-login>` `<scopes>`, `<reviewer-login>` `<scopes>`;
  Project steps `<run as login>`; current milestone `<M*>`.

## 1. Identities and shared state

| Bot | Role | `gh` identity |
|---|---|---|
| `<CoordinatorBot>` | Coordinator | `GH_TOKEN=$(gh auth token --user <author-login>)`; `<reviewer-login>` for steering signals |
| `<BuilderBot>` | Builder | `<author-login>` |
| `<ReviewerBot>` | Reviewer-validator | `<reviewer-login>` for all reviews |
| `<SynthesizerBot>` | Synthesizer | `<author-login>` |

Shared state: `<state-dir>/<owner>__<repo>/` with `claims/`,
`locks/merge.lock`, `reviewer-engines.md`, `sweeper-state.json`.
Labels: the ten `crew:*` labels, created `<date>` (status: applied).
Project: `<project-number>` (Todo, In Progress, In Review, Done) | none.

## 2. Routines per bot

| Routine | Bot | Trigger | Status |
|---|---|---|---|
| B1 build intake | `<BuilderBot>` | `issue-assigned`, allowlist `<user-logins>` | `<planned \| live>` `<date>` |
| B2 per-PR watch | `<BuilderBot>` | PR-scoped: `ci-failed`, `review-changes-requested`, `pr-merged`, `pr-closed` | created per PR by `<BuilderBot>` |
| V1 PR intake | `<ReviewerBot>` | `pr-opened`, no allowlist | `<planned \| live>` `<date>` |
| V2 per-PR watch | `<ReviewerBot>` | PR-scoped: `ci-passed`, `review-requested`, `pr-merged`, `pr-closed` | created per PR by `<ReviewerBot>` |
| S1 merge on approval | `<SynthesizerBot>` | `review-approved`, no allowlist | `<planned \| live>` `<date>` |
| A1 after merge | `<CoordinatorBot>` | `pr-merged`; `ci-failed` on `<default-branch>` (only if push CI) | `<planned \| live>` `<date>` |
| A2 steering dispatcher | `<CoordinatorBot>` | `pr-comment`, `inline-review-comment`, allowlist `<user-logins>` | `<planned \| live>` `<date>` |
| A3 stuck-PR sweeper | `<CoordinatorBot>` | schedule, `<timezone>` | `<planned \| live>` `<date>` |

Routine IDs: B1 `<id>`, V1 `<id>`, S1 `<id>`, A1 `<id>`, A2 `<id>`, A3 `<id>`.
Not subscribed: `review-commented`, `pr-pushed`, `review-thread-*`.

## 4. Enforcement steps (all reversible)

1. `<reviewer-login>` write collaborator: `<done, date>`.
2. `<default-branch>` protection level `<A | B | C>`: `<done, date>`.
3. Squash-only merges, delete-branch-on-merge: `<done, date>`.
4. Only the synthesizer merges: convention.

## 8. Pilot findings

Dated entries appended as the crew learns (see Known gaps in the runbook).
````

Sections 3, 5, 6 and 7 of the template (state passing, cutover, wake cost, open
risks) are copied unchanged and extended only where this repo differs.

## Step 7: listener wiring per bot

A routine is created on the bot that owns it, from its rendered file under
`<out-dir>/runtime/` ([Step 0](#step-0-write-validate-and-render-the-profile)),
or from the template file with every install-time placeholder replaced by hand
(the hand-fill fallback). How a routine is created is platform-specific; the
templates give the trigger JSON and prompt text
([../templates/README.md](../templates/README.md)).

The templates carry the merge-up rule
([#20](https://github.com/mw-ding/eng-crew/issues/20)): a clean merge-up after
APPROVE gets a formal merge-up re-approve at the new head with the same round
number; after CHANGES, a COMMENT ack with no round and no verdict; a behavior-
or content-changing resolution gets a normal round; and the synthesizer gate
never accepts a `pass=ack`. See
[reviewer-v2-watch.md](../templates/runtimes/grok-bot/reviewer-v2-watch.md) and
[synthesizer.md](../templates/runtimes/grok-bot/synthesizer.md). No override is needed when
filling V2 and S1.

Rules that apply to all:

- Each event has exactly one consuming role. Only the steering dispatcher
  holds `pr-comment` and `inline-review-comment`; nobody holds
  `review-commented`.
- **A routine run cannot create or delete routines.** A wake that needs a
  per-PR watch hands the request to its parent bot turn, which creates it
  ([routine limits](../templates/README.md#routine-limits)).
- Every per-PR watch lists `pr-merged` and `pr-closed`, and deletes itself
  after that terminal wake.
- A single watch covers only a few repos (4 on the pilot platform); this matters
  only for repo-wide forwarding across many repos.
- Every wake costs a full bot turn. Keep triggers tight.

| Bot | Standing routines (repo-wide) | Per-PR watches | Template files |
|---|---|---|---|
| `<CoordinatorBot>` | A1 after merge; A2 steering dispatcher; A3 stuck-PR sweeper | None by default. Optional comment-event watch on one external PR, created by the coordinator's parent turn when the user wants to steer it | [coordinator-after-merge.md](../templates/runtimes/grok-bot/coordinator-after-merge.md), [coordinator-steering-dispatcher.md](../templates/runtimes/grok-bot/coordinator-steering-dispatcher.md), [coordinator-stuck-pr-sweeper.md](../templates/runtimes/grok-bot/coordinator-stuck-pr-sweeper.md) |
| `<BuilderBot>` | B1 build intake (`issue-assigned`) | B2, created by `<BuilderBot>`'s parent turn right after its worker opens PR `<n>` | [builder-b1.md](../templates/runtimes/grok-bot/builder-b1.md), [builder-b2.md](../templates/runtimes/grok-bot/builder-b2.md) |
| `<ReviewerBot>` | V1 PR intake (`pr-opened`) | V2, created by `<ReviewerBot>`'s parent turn after V1 acks PR `<n>` | [reviewer-validator.md](../templates/runtimes/grok-bot/reviewer-validator.md), [reviewer-v2-watch.md](../templates/runtimes/grok-bot/reviewer-v2-watch.md), [reviewer-engines.md](../templates/runtimes/grok-bot/reviewer-engines.md) |
| `<SynthesizerBot>` | S1 merge on approval (`review-approved`) | None | [synthesizer.md](../templates/runtimes/grok-bot/synthesizer.md) |
| Researcher | None | None | None |

Who creates what, in order, for one PR:

| When | Created by | Routine |
|---|---|---|
| Once, at install | Each bot's owner | B1, V1, S1, A1, A2, A3 |
| After the PR opens | `<BuilderBot>` parent turn | B2 for PR `<n>`, then verified (lists routines, checks the four events, writes the routine folder id to `watches/pr-<n>.b2`, posts the full-SHA `pass=watch` marker). B1 only requests this hand-off. Lighter-lane PRs skip B2 ([protocol §6](protocol.md#6-duties-on-wake-all-roles)) |
| After V1 acks the PR | `<ReviewerBot>` parent turn | V2 for PR `<n>` |
| On `pr-merged` or `pr-closed` | The watch itself | Deletes itself (B2, V2) |

The per-routine details that matter when filling the templates:

- **B1** allowlist is `<user-logins>`; it gates the **assigner**, so an outsider
  cannot wake the builder. Its prompt carries `<toolchain-bin>` and the
  closing-keyword rule (`Closes #<n>` or `Refs #<n>`).
- **B2** carries `ci-failed`, `review-changes-requested`, `pr-merged` and
  `pr-closed` for its PR; `<n>` becomes a JSON number when the watch is created.
  The builder's parent turn verifies it right after creating it and records its
  routine folder id (not a platform UUID) in `watches/pr-<n>.b2`.
- **V1** has no allowlist, so external PRs are covered. Fill in how scratch or
  E2E PRs are ignored and which base branch counts (`<default-branch>`).
- **V2** reads `reviewer-engines.md` fresh on each run.
- **S1** has no allowlist. It acts only when the merge gate holds at head.
- **A1** drops its second listener if `<default-branch>` has no push CI.
- **A2** allowlist is `<user-logins>` and gates the PR **author**; the prompt
  checks the **commenter** itself.
- **A3** needs `<timezone>` and an unused minute in its cron expression; use
  the platform's own schedule syntax.

Record each routine's ID, name and trigger JSON in the wiring doc as it is
created; the checklist asks for them. After a routine is live, flip its row in
the wiring doc from `planned` to `live` with the date.

### Steering wiring

Steering commands are comments whose first line starts with the steering prefix
(see the table in [protocol.md](protocol.md#9-steering-crew-commands)). Single
dispatcher: the coordinator (A2). Owners wake through the normal listeners
(`review-changes-requested` for rework, `review-requested` for rereview,
`review-approved` for the merge override), so no extra listener is needed. The
commands are accepted only from `<user-logins>`, and bots never write a line
that starts with the prefix.

### Cutover for existing open PRs

For PRs that predate the listeners, follow
[wiring.md section 5](../templates/runtimes/grok-bot/wiring.md#5-cutover-plan-for-open-prs):
install the routines, backfill the per-PR watches in one pass, post a
`cutover` marker on each PR, label each `crew:changes` or `crew:hold` as
appropriate, and kick them in dependency order. Do not edit PR bodies. A cutover
PR is exempt from the builder `pass=watch` merge gate only until its builder
posts its `[<BuilderBot>/watch]` review or any builder `crew:v1` marker after
the cutover (by post time, whatever commit it sits on, including attaching B2 at
the unchanged cutover SHA); from then on a valid full-SHA `pass=watch` marker
is required, and the synthesizer holds and priority-pings the builder if it is
missing or malformed. Skip this for a repo with no open PRs.

## Step 8: first test issue

Use a trivial, low-risk issue that touches only docs, so a failure costs
nothing. It should be small enough for the trivial tier ([roles.md](roles.md#tiers))
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

### Expected event and marker sequence

Capture the timestamp and the evidence for every row; the checklist references
this table. Bot output is always a review body, never a plain comment.

| # | Stage | Event / trigger | Who acts | Expected GitHub state and markers |
|---|---|---|---|---|
| 1 | Spec and handoff | Issue created; `crew:ready` added | `<CoordinatorBot>` | Issue with numbered criteria. No wake: labels fire nothing |
| 2 | Handoff | `issue-assigned` | B1 wakes `<BuilderBot>` | Claim file for the issue under `claims/`; the builder checked `crew:ready`, no existing PR or branch |
| 3 | Build | Worker runs, toolchain pinned, push | `<BuilderBot>` worker | Branch `<role>/<n>-<slug>`; worker never posts to GitHub |
| 4 | PR | PR opened non-draft | `<BuilderBot>` | Body has `## Context` with `Closes #<n>` (or `Refs`), `## Changes Made`, `## Testing Done`, `## Test Output`, `## Acceptance Evidence`, `## Risks / Not Done`, and the line `<!-- crew:v1 role=builder issue=<n> tier=<tier> engine=<engine> model=<model> -->` before the signature. Label `crew:in-review`. Project item added. `pr-opened` fires |
| 5 | Intake | `pr-opened` | V1 wakes `<ReviewerBot>` | COMMENT review `[<ReviewerBot>/ack]`, marker `pass=ack`, as `<reviewer-login>`. V1 hands V2 creation to the `<ReviewerBot>` parent turn. B2 is not created at this step: `pr-opened` wakes only the reviewer |
| 6 | Steering no-op | `pr-comment` from the ack | A2 wakes `<CoordinatorBot>` | Ends at once, posts nothing. One expected extra wake per bot post |
| 7 | CI | Checks settle | GitHub Actions | `ci-passed` wakes V2. A `ci-failed` instead wakes B2: `[<BuilderBot>/ci-fix]` COMMENT review, at most 3 attempts |
| 8 | Review and validation | `ci-passed` | V2 wakes `<ReviewerBot>` | Review engine differs from the builder engine. Claim file `reviewer-validator-pr<n>-<sha7>` taken and deleted. Separate review and validation workers in unique worktrees |
| 9 | Verdict | Formal review at head | `<ReviewerBot>` as `<reviewer-login>` | One review per head SHA. `[<ReviewerBot>/verdict] round 1`, review and validation sections each with a marker, final line `<!-- crew:v1 role=reviewer-validator pass=verdict pr=<n> sha=<head-sha> round=1 verdict=pass -->`. In one step: `crew:approved` set, `crew:in-review` removed |
| 9a | Iterate (if changes) | `review-changes-requested` | B2 wakes `<BuilderBot>` | `verdict=changes`, `crew:changes`. Builder pushes and posts `[<BuilderBot>/fix] round 1 @ <sha7>`. CI, then a round-2 verdict. A third `REQUEST_CHANGES` escalates |
| 10 | Merge | `review-approved` | S1 wakes `<SynthesizerBot>` | Gate re-checked at head. `locks/merge.lock` taken. `gh pr merge <n> --squash --match-head-commit <sha>`. `[<SynthesizerBot>/merge]` COMMENT review, marker `pass=merge`. Branch deleted if configured |
| 11 | Close-out | `pr-merged` | A1 (`<CoordinatorBot>`), B2 (`<BuilderBot>`), V2 (`<ReviewerBot>`) | Issue closed (by `Closes`, or by the coordinator for `Refs`). `crew:ready` removed from the issue, `crew:in-review` gone from the PR. Project item Done. Builder deleted its worktrees and build output. B2 and V2 deleted themselves |
| 12 | Default-branch CI | Push run on the merge commit | GitHub Actions | Green. A failure fires `ci-failed` on `<default-branch>` and A1 files a fix issue; it does not touch the branch |

The trivial issue is expected to be approved in round 1; one fix round is
acceptable and exercises the iterate path. If the run needs more than two
nudges from a person, stop and find out which listener missed (see the wake
timeline in the checklist).

### Optional steering smoke test

On the test PR before merge, as one of `<user-logins>`, post a comment whose
first line is the hold command (the `/crew` prefix plus `hold`; write it in the
PR comment box, never in a doc or script). Expect: `crew:hold` added and a
`[<CoordinatorBot>/steer] ack hold` COMMENT review with
`pass=steer cmd=hold cmd-id=<comment id>`. Repeat with the resume command and
expect the label removed and a `resume` marker. Do this only if the steering
dispatcher is live.

## Verification checklist

Do not tick an item without its evidence. Paste the output, ID, URL or marker
line into an evidence file for the repo (modelled on the pilot's evidence
file: result, links, a timeline table, then gaps found) and link it from the
wiring doc. Never paste a token; command output that contains one must be
redacted before it is saved.

Verify that the V2 and S1 prompts carry the
[merge-up rule](#step-7-listener-wiring-per-bot): no `pass=ack` passes the merge gate.

| # | Check | Evidence to capture | Passes when |
|---|---|---|---|
| P1 | Profile validates | Output of `crew-config.py validate crew.toml` and of `crew-config.py resolve --project crew.toml` ([Step 0](#step-0-write-validate-and-render-the-profile)) | Both exit 0; no `<...>` value in `crew.toml` or the resolve output; the state dir holds the same `crew.toml` |
| P2 | Render clean | Output of `crew-render.py` with the written paths | Exit 0 with `crew-render: OK`, no `file:line: reason` line; the hand-fill fallback, if used, recorded in the wiring doc |
| P3 | Parity (Grok Bot) | Output of `python3 scripts/test-render-parity.py` | Exit 0 with `OK`: rendered default-profile routines match the template text |
| 1 | Identities and scopes | `gh api user --jq .login` for each identity; the scopes header for each | Two different logins; `repo` on both; `project` present on the identity running Project operations (delegation recorded) |
| 2 | Labels | Output of `gh label list -R <owner>/<repo> --search crew: --json name,color,description` | Ten rows with the names, colors and descriptions from step 1 |
| 3 | Reviewer access | Output of the collaborator `permission` call; pending invitation count | `write` and `0` pending |
| 4 | Milestones + Project | Milestone list and issue assignments; `<project-number>` and URL; Status option names | M1, M2, … milestones used; closed `M*` frozen (no new issues, follow-ups in next `M*`); board linked to repo with Todo, In Progress, In Review, Done |
| 5 | CI facts | Workflow list with triggers; latest push run on `<default-branch>` (URL); check names on a green head | Required check names written in the wiring doc; push CI status stated |
| 6 | Branch protection and merge settings | Protection JSON or the 404; merge-settings output | Matches the level chosen in step 4 |
| 7 | Product safety | Hooks and labels listing; the written decision on other automation, product labels, E2E PRs, fork handling, workflow changes | Only one automation system owns the repo; no product label or command touched; no workflow deleted in a way that removes push CI |
| 8 | State dir | `ls -la` of the state dir and `claims/`; `locks/merge.lock` present | Writable by every bot account; `wiring.md` and `reviewer-engines.md` filled |
| 9 | Routines | For each of B1, V1, S1, A1, A2, A3: routine ID, name, trigger JSON as created; the wiring doc rows showing `live` with a date | Six standing routines; triggers match the templates; no `review-commented` subscription |
| 10 | Test issue | Issue URL; label list; assignment time; claim file name | `crew:ready` present at assignment; one builder wake |
| 11 | PR | PR URL; body sections present; the builder marker line; `crew:in-review` time | Non-draft; all sections; engine and model named are the ones actually used |
| 12 | Intake | `[<ReviewerBot>/ack]` review id and its marker line; the routine folder ids of the B2 and V2 watches | Ack is a COMMENT review as `<reviewer-login>`; both watches exist and were created by parent turns; the B2 marker file `<state-dir>/<owner>__<repo>/watches/pr-<n>.b2` and the builder `pass=watch` marker are present |
| 13 | CI at head | Check runs at the verdict head (names, conclusions) | Every required check green at head |
| 14 | Verdict | Review id; the `pass=verdict` marker line; review and validation marker lines; builder engine vs reviewer engine | One formal review per head SHA; reviewer engine differs from the builder engine; `round` is correct |
| 15 | Label hygiene | Labels after the verdict | `crew:approved` set, `crew:in-review` removed in the same step |
| 16 | Merge | Merge commit SHA; the `[<SynthesizerBot>/merge]` review id and marker; approval-to-merge time | Squash merge at the approved head SHA; merge gate re-checked; branch deleted |
| 17 | Close-out | Issue state and closing time; labels on issue and PR; Project item status; worktree removal; the B2 and V2 watches gone | Issue closed; `crew:ready` and `crew:in-review` cleared; item Done; both watches deleted themselves |
| 18 | Default-branch CI after merge | Push run URL for the merge commit | Green, or a filed fix issue |
| 19 | Comment discipline | The list of bot-authored items on the PR: reviews only | No plain PR comments or inline comments by bots; no line starting with the steering prefix in any bot text or commit message |
| 20 | PR body untouched | GraphQL `userContentEdits` for the PR body | No edits after creation |
| 21 | Wake timeline | The timeline table below, filled | Every stage woke exactly one consumer; extra wakes explained (ack and bot posts wake the dispatcher once each) |
| 22 | Steering (if live) | Ack review ids and `cmd-id` markers for the hold and resume smoke test | Ack posted once per command id; label toggled |
| 23 | Rollback rehearsed on paper | The rollback steps below, with the IDs from item 9 | Every routine ID needed to remove the crew is written down |

Check item 20 with:

```bash
gh api graphql -f query='
  query($owner: String!, $repo: String!, $number: Int!) {
    repository(owner: $owner, name: $repo) {
      pullRequest(number: $number) { userContentEdits(first: 5) { totalCount } }
    }
  }' -f owner=<owner> -f repo=<repo> -F number=<n>
```

### Evidence timeline

Fill one row per event, as the pilot did. Times in one timezone.

| # | Time | Stage | Event / trigger | Bot (identity) | Evidence |
|---|---|---|---|---|---|
| 1 | `<time>` | Handoff | `issue-assigned` | `<CoordinatorBot>` → B1 | claim file name |
| 2 | `<time>` | PR | PR opened, `crew:in-review` | `<BuilderBot>` (`<author-login>`) | PR URL, builder marker |
| 3 | `<time>` | Intake | `pr-opened` → V1 | `<ReviewerBot>` (`<reviewer-login>`) | ack review id |
| 4 | `<time>` | Watches | B2 and V2 created | parent turns | routine IDs |
| 5 | `<time>` | CI | checks green at `<sha7>` | GitHub Actions | check-run summary |
| 6 | `<time>` | Verdict | `ci-passed` → V2 | `<ReviewerBot>`, `<engine>` | review id, marker line |
| 7 | `<time>` | Merge | `review-approved` → S1 | `<SynthesizerBot>` (`<author-login>`) | merge SHA, merge review id |
| 8 | `<time>` | Close-out | `pr-merged` → A1, B2, V2 | `<CoordinatorBot>`, `<BuilderBot>` | issue closed, worktree removed |

Add one row per fix round, merge-up and nudge. List any gap found at the end
("Gaps found"), the way the pilot did, and turn each into an issue.

## Rollback and offboarding

Everything the runbook did is reversible. Do it in this order so no bot acts on
a half-removed setup.

1. **Pause.** Add `crew:hold` to every open crew PR and `crew:ready` issue so
   every bot no-ops: `gh pr edit <n> -R <owner>/<repo> --add-label crew:hold`.
   Tell the user which PRs and issues are in flight.
2. **Remove the routines**, newest first, using the IDs recorded in checklist
   item 9. A routine run cannot delete routines, so this is done from each
   bot's parent turn:
   - The per-PR watches B2 and V2 for every open PR.
   - The standing routines B1, V1, S1, A1, A2 and A3.
   Mark each row `removed` with a date in the wiring doc. Confirm no wake
   arrives for a new comment or assignment.
3. **Revoke the collaborator** if the reviewer account should no longer have
   access. This also stops its reviews from counting:

   ```bash
   GH_TOKEN=$(gh auth token --user <author-login>) \
     gh api -X DELETE repos/<owner>/<repo>/collaborators/<reviewer-login>
   # a pending, unaccepted invitation instead:
   GH_TOKEN=$(gh auth token --user <author-login>) \
     gh api -X DELETE repos/<owner>/<repo>/invitations/<invitation-id>
   ```

4. **Undo enforcement** if the owner wants the old settings back: remove or
   relax branch protection, and restore the merge settings recorded in the
   evidence from step 4:

   ```bash
   GH_TOKEN=$(gh auth token --user <author-login>) \
     gh api -X DELETE repos/<owner>/<repo>/branches/<default-branch>/protection
   ```

5. **Labels are optional.** The ten `crew:*` labels are harmless and can stay.
   To remove them, delete each one (this also strips it from issues and PRs;
   do it only after step 1 has paused everything):

   ```bash
   for l in ready in-review changes approved escalated hold external spec needs-md needs-mirror; do
     GH_TOKEN=$(gh auth token --user <author-login>) gh label delete "crew:$l" -R <owner>/<repo> --yes
   done
   ```

6. **Project.** Unlink or keep it: `gh project unlink <project-number> --owner <owner> --repo <repo>`.
   Close or delete it only if the owner agrees.
7. **State dir.** Archive `<state-dir>/<owner>__<repo>/` (keep `wiring.md` and
   the evidence file) and remove `claims/` and `locks/`. Delete leftover worker
   worktrees and build output for the repo.
8. **Open PRs.** Hand them back to their authors. Do not post a farewell
   comment; remove `crew:hold` once the routines are gone.
9. **Record it.** Add a dated entry to the wiring doc and the evidence file
   saying what was removed and what was kept, and file an issue for anything
   that did not roll back cleanly.

## Known gaps

Open items found while writing this runbook. Each follow-up is tracked as an
eng-crew issue:

- The templates' own open items still apply
  ([../templates/README.md](../templates/README.md#open-items)).
- Creating and deleting routines is platform-specific and not scripted in this
  repo; this runbook names what to create, not the platform call.
  [#27](https://github.com/mw-ding/eng-crew/issues/27) tracks a scripted routine
  installer for a new repo.
- "Only the synthesizer merges" is convention while the bots share an account.
  This limitation is by design for now, with no follow-up issue.
- Evidence a verdict depends on should be committed on the PR branch, not on a
  side branch. A change that does not move the PR head wakes no one and needs a
  manual rereview steer (lesson of Oct 20, 2026). The protocol now covers this
  (see [evidence requirements](protocol.md#3-evidence-requirements)).
