# Runbook: put the crew on a new repo

This runbook takes a repo from "no automation" to "one issue went through every
stage, merged, and closed out, with evidence". It ends with a verification
checklist. Do the steps in order and capture the evidence named in each step;
the [checklist](#verification-checklist) collects it.

The install path starts with `crew bootstrap`: write one `crew.toml`, preview
the install, then apply it ([Step 0](#step-0-write-validate-and-render-the-profile)).
The profile ([profile.md](profile.md)) replaces hand-filled placeholders.
The manual validate, resolve, render and state setup remain below as a fallback.
Then complete the GitHub install mechanics (Steps 1 to 4: labels, reviewer collaborator,
milestones and board, CI and protection;
[GitHub backend: Tracking](backends/github.md#tracking)), the product-safety
checks (Step 5), the state dir and routines from the rendered output (Steps 6
and 7), and a first test issue (Step 8).
For a local tmux crew instead of Grok Bot, see [tmux runtime](#tmux-runtime).

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

Moved to
[Prerequisites](runbooks/prerequisites.md#prerequisites): do not start until
every prerequisite is true, and record the evidence in the checklist. The
module holds [Identities](#identities),
[Per-identity `gh` usage](#per-identity-gh-usage),
[Token scopes](#token-scopes), [Shared state dir](#shared-state-dir) and
[Other prerequisites](#other-prerequisites).

### Identities

Moved to
[Prerequisites: Identities](runbooks/prerequisites.md#identities):
the author identity `<author-login>` and the reviewer identity
`<reviewer-login>`, which must be a different account, and who may run the
admin setup steps.

### Per-identity `gh` usage

Moved to
[Prerequisites: Per-identity `gh` usage](runbooks/prerequisites.md#per-identity-gh-usage):
never switch the active `gh` account, select the credential per command or
export it for one shell only, never print, paste or commit a token value, and
check that both identities exist on the box.

### Token scopes

Moved to
[Prerequisites: Token scopes](runbooks/prerequisites.md#token-scopes): the
scopes each identity and the setup account need, the fine-grained
equivalents, the scope check, the two options when `project` is missing, and
that a GitHub Project is required for every crew repo.

### Shared state dir

Moved to
[Prerequisites: Shared state dir](runbooks/prerequisites.md#shared-state-dir):
the one per-repo directory `<state-dir>/<owner>__<repo>/` shared by all bots,
its six paths, and that it is writable by every bot account, outside any repo
checkout and holds no credentials.

### Other prerequisites

Moved to
[Prerequisites: Other prerequisites](runbooks/prerequisites.md#other-prerequisites):
the reviewer-validator engine and private-repo conditions, the known and
pinned toolchain, and the human owner approvals bots cannot give.

## Step 0: write, validate and render the profile

Both install paths live in [Profile install](runbooks/profile-install.md):

1. [Bootstrap (recommended)](runbooks/profile-install.md#bootstrap-recommended).
2. [Manual fallback](runbooks/profile-install.md#manual-fallback), when
   bootstrap is unavailable.

### Bootstrap (recommended)

Moved to
[Profile install: Bootstrap (recommended)](runbooks/profile-install.md#bootstrap-recommended):
install from a verified release bundle or exact release tag (`--dev` for an
untagged checkout), dry-run then apply `crew bootstrap`, handle refusals and
review, check the expected outputs and the runtime-specific deployment, then
complete Steps 1–8.

### Manual fallback

Moved to
[Profile install: Manual fallback](runbooks/profile-install.md#manual-fallback):
when bootstrap is unavailable, write, validate and resolve `crew.toml`, render
the role briefs and runtime artifacts, or hand-fill the templates, and record
the fallback and its reason in `wiring.md`.

## Step 1: create the `crew:*` labels

Moved to
[GitHub tracking: Step 1](runbooks/github-tracking.md#step-1-create-the-crew-labels):
list the existing `crew:*` namespace first and stop on a collision, create
the ten labels with the guarded `--force` loop (or the API call), and verify
exactly ten rows with the expected colors and descriptions. Milestones and
the Project board stay in [Step 3](#step-3-create-milestones-and-link-a-github-project-v2).

## Step 2: add the reviewer as a collaborator

Moved to
[GitHub reviewer access: Step 2](runbooks/github-reviewer-access.md#step-2-add-the-reviewer-as-a-collaborator):
invite the reviewer identity with write access, accept the invitation (or
the existing-org-member path), verify `write` permission and zero pending
invitations, and confirm the author identity's push access.

## Step 3: create Milestones and link a GitHub Project (v2)

Moved to
[GitHub tracking: Step 3](runbooks/github-tracking.md#step-3-create-milestones-and-link-a-github-project-v2):
create the current `M*` milestone (a closed milestone is frozen), keep the
board item status current, check the `project` scope first
([Token scopes](#token-scopes)), create and link the Project, set exactly
four Status options (settings page, or the GraphQL replacement only while the
project is empty), keep the board workflows from conflicting, verify, and
record `<project-number>` and the current `M*` milestone in the wiring doc.

## Step 4: check CI and branch protection

Moved to
[GitHub CI and branch protection: Step 4](runbooks/github-ci-protection.md#step-4-check-ci-and-branch-protection):
list the workflows and their `on:` triggers, check push CI on
`<default-branch>` (the after-merge `ci-failed` listener and noisy-job
handling), find the exact required check names (prefer one aggregate check),
and read the current protection, rulesets and merge settings (a 404 is normal
for an unprotected branch).

Moved to
[GitHub CI and branch protection: Protection choice](runbooks/github-ci-protection.md#protection-choice):
item 5, choose protection level A, B or C with the owner (all reversible
through [Rollback](#rollback-and-offboarding)), with the level C apply and
remove example, the `app_id` note, why stale approvals stay valid and the
check that no workflow pushes to `<default-branch>`. This moves
documentation only; it applies no settings.

Moved to
[GitHub CI and branch protection: Merge settings and enforcement limits](runbooks/github-ci-protection.md#merge-settings-and-enforcement-limits):
items 6 and 7, squash-only merges and branch cleanup on `<default-branch>`
(merge-ups still create merge commits on PR branches) with the full settings
command, and the limit that "only the synthesizer merges" stays a convention
while bots share an account, with the
[merge enforcement](merge-enforcement.md) link; capture the outputs of items
1 to 6 for the checklist.

## Step 5: product-safety checks

Moved to
[Product preflight: Automation, namespace and fork preflight](runbooks/product-preflight.md#automation-namespace-and-fork-preflight):
do these before installing any routine, since installing routines makes the
crew live, and write the answers in the wiring doc's section 0 ("Facts found
in the repo"); item 1, one automation system per repo; item 2, never touch the
product's own labels or commands; item 3, fork PRs and external contributors.
Items 4 to 8 moved to
[Product preflight: Workflow, repo-contract, toolchain and cutover checks](runbooks/product-preflight.md#workflow-repo-contract-toolchain-and-cutover-checks):
item 4, no workflow deletion that removes push CI on the default branch; item
5, repo rules that change the crew's wording; item 6, toolchain; item 7,
existing open PRs and issues; item 8, deploy secrets.

## Step 6: state dir and wiring doc

Moved to
[Grok Bot onboarding: Step 6](runbooks/grok-onboarding.md#step-6-state-dir-and-wiring-doc):
verify bootstrap's recorded install (`VERSION`, `install.json`, the state
listing) against the reviewed plan, keep bootstrap-owned files intact, copy
the deployed Grok Bot `wiring.md` if missing, then the manual-fallback state
setup, filling `wiring.md` from the deployed or rendered copy with
`planned`/`applied`/`live` status, `reviewer-engines.md` and the README seed.
The module also holds the worked example; its entry is
[Filled-in wiring.md](#filled-in-wiringmd-derived-from-the-template) below.

### Filled-in wiring.md (derived from the template)

Moved to
[Grok Bot onboarding: Filled-in wiring.md](runbooks/grok-onboarding.md#filled-in-wiringmd-derived-from-the-template):
the complete worked `wiring.md` after steps 1 to 6, with placeholders, the
pilot-observation qualification, the routine table, IDs and unsubscribed
events, and the note on template sections 3, 5, 6 and 7.

## Step 7: listener wiring per bot

Moved to
[Grok Bot onboarding: Step 7](runbooks/grok-onboarding.md#step-7-listener-wiring-per-bot):
the rendered or hand-filled routine origins, the Grok Bot
[cross-runtime limits](runtimes/grok-bot.md#cross-runtime-limits), the
merge-up rule with its re-approve, ack and normal-round distinctions and the
`pass=ack` exclusion, the five rules for all routines, the per-bot ownership
table and the creation-order table for one PR, then the
[per-routine details](runbooks/grok-onboarding.md#per-routine-details) for
B1 to A3 and recording each routine as it goes live. Its two child sections
keep their entries below.

### Steering wiring

Moved to
[Grok Bot onboarding: Steering wiring](runbooks/grok-onboarding.md#steering-wiring):
the single coordinator dispatcher (A2), the normal listeners that wake
owners, the `<user-logins>` allowlist and that bots never write a line that
starts with the steering prefix.

### Cutover for existing open PRs

Moved to
[Grok Bot onboarding: Cutover for existing open PRs](runbooks/grok-onboarding.md#cutover-for-existing-open-prs):
the one-pass backfill, `cutover` markers, labels and dependency-order kicks,
no PR body edits, and the cutover exemption from the builder `pass=watch`
merge gate, when it ends and the synthesizer hold and ping after it.

## Step 8: first test issue

Moved to
[Onboarding proof: Step 8](runbooks/onboarding-proof.md#step-8-first-test-issue):
use a trivial, low-risk, docs-only issue small enough for the trivial tier
that exercises every stage once.

### Template issue

Moved to
[Onboarding proof: Template issue](runbooks/onboarding-proof.md#template-issue):
the smoke issue title and full Markdown body (goal, acceptance criteria, out
of scope, role and tier hint), creating it with `crew:ready` and then
assigning it to `<author-login>` (the assignment is the event), the milestone
and Project placement, and the `Refs #<n>` path when closing keywords are
forbidden.

### Expected event and marker sequence

Moved to
[Onboarding proof: Expected event and marker sequence](runbooks/onboarding-proof.md#expected-event-and-marker-sequence):
the stage table from issue creation to default-branch CI, including the
conditional iterate row 9a, with the timestamp and evidence to capture per
row, and the round-1 expectation and two-nudge limit.

### Optional steering smoke test

Moved to
[Onboarding proof: Optional steering smoke test](runbooks/onboarding-proof.md#optional-steering-smoke-test):
the hold and resume check on the test PR, only if the steering dispatcher is
live.

## Verification checklist

Moved to
[Onboarding proof: Verification checklist](runbooks/onboarding-proof.md#verification-checklist):
tick no item without its evidence and never record a token; the V2 and S1
merge-up check; the P1–P3 and 1–23 rows with their evidence and pass
conditions; and the item-20 GraphQL query for PR body edits.

### Evidence timeline

Moved to
[Onboarding proof: Evidence timeline](runbooks/onboarding-proof.md#evidence-timeline):
one row per event in one timezone, plus one row per fix round, merge-up and
nudge, and the "Gaps found" list, each gap filed as an issue.

## tmux runtime

Steps 0 to 8 above describe the Grok Bot wiring after bootstrap. This section runs the same
pipeline as a local tmux crew instead: one tmux session per repo, one window
per agent, driven by the `crew` CLI. The design and every command's exact
behaviour are in the [tmux binding](runtimes/tmux.md#usage); this is the
operator's path. Below, `crew` means `<eng-crew>/scripts/crew`, and every
command also takes `--project "$CREW_PROJECT"`. Every window gets
`CREW_PROJECT`, the absolute path of the `crew.toml` given to `crew up`; in
your own shell, export it first (`export CREW_PROJECT=<project>/crew.toml`,
absolute).

This section is now navigation: each heading below keeps its anchor and
links to its module. The current steps are in the
[tmux onboarding module](runbooks/tmux-onboarding.md); the dated
2026-10-30 run is in the
[tmux onboarding history](runbooks/tmux-onboarding-history.md).

### tmux prerequisites

Moved to
[tmux onboarding: tmux prerequisites](runbooks/tmux-onboarding.md#tmux-prerequisites):
tools and logins, engines, permission mode, Codex hook trust, the bundle or
checkout, and the nested-sandbox variable.

### Set up the target repo

Moved to
[tmux onboarding: Set up the target repo](runbooks/tmux-onboarding.md#set-up-the-target-repo):
the profile and its path placeholders, the labels and the CI check.

### Run the crew

Moved to
[tmux onboarding: Run the crew](runbooks/tmux-onboarding.md#run-the-crew):
the command table, the first-start trust answer, the one-shot watcher, close-out
and owner duties.

### tmux troubleshooting

Moved to
[tmux onboarding: tmux troubleshooting](runbooks/tmux-onboarding.md#tmux-troubleshooting):
every symptom, cause and fix, including the no-blind-input rules.

### End-to-end run (2026-10-30)

Moved to
[tmux onboarding history: End-to-end run (2026-10-30)](runbooks/tmux-onboarding-history.md#end-to-end-run-2026-10-30):
the dated #139 run at `7eb454d`, its timeline and the pass bar adopted then.
History, not current instructions.

## Rollback and offboarding

From a host terminal outside the crew session, preview a bootstrap-managed
install with `crew bootstrap --project <project>/crew.toml
--uninstall --dry-run`, then apply with `--uninstall --yes`. This pauses open
crew PRs and ready issues, stops tmux while preserving run files and worktrees,
removes unchanged untracked install targets and their exclude entries, and archives
state beside its original location. Unlanded runs block target removal and
archival after the runtime stops. Edited targets, leftover worktrees, wiring
and evidence are kept. Labels stay unless `--remove-labels` is explicit.
Grok Bot pauses items first and waits for manual routine removal; after marking
the IDs in `wiring.md` removed and checking no new wakes, retry with
`--routines-removed`. Project, collaborator and protection changes stay human
steps. The archived `install.json` records removed and kept paths. Open PRs
remain held until their authors take them back.

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

Moved to
[Onboarding proof: Known gaps](runbooks/onboarding-proof.md#known-gaps): the
open items found while writing this runbook, each tracked as an eng-crew
issue or recorded as a limitation by design.
