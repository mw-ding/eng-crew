# Grok Bot onboarding

Onboarding module for the Grok Bot install state and wiring, split out of the
[onboarding runbook](../runbook-new-repo.md) under the M26 modular
organization principle
([#676](https://github.com/mw-ding/eng-crew/issues/676)). It holds the
runbook's
[Step 6: state dir and wiring doc](#step-6-state-dir-and-wiring-doc): the
install-state verification and the four wiring setup items, after
[Step 5: product-safety checks](../runbook-new-repo.md#step-5-product-safety-checks),
and its worked
[Filled-in wiring.md](#filled-in-wiringmd-derived-from-the-template)
example, and the opening of
[Step 7: listener wiring per bot](#step-7-listener-wiring-per-bot): the
routine origins, the Grok Bot limits, the merge-up rule, the rules for all
routines and the two ownership and creation-order tables. Step 7's
per-routine details,
[Steering wiring](../runbook-new-repo.md#steering-wiring) and
[Cutover for existing open PRs](../runbook-new-repo.md#cutover-for-existing-open-prs)
remain in the runbook.

## Step 6: state dir and wiring doc

After bootstrap, verify its recorded install before filling the wiring doc:

```bash
cat <state-dir>/<owner>__<repo>/VERSION
cat <state-dir>/<owner>__<repo>/install.json
ls -la <state-dir>/<owner>__<repo>/ <state-dir>/<owner>__<repo>/claims
```

Confirm the source, runtime, profile copy and pending human steps match the
reviewed plan. Keep bootstrap-owned files intact; rerun bootstrap for profile
changes. For Grok Bot, copy the deployed `paths.live_dir/runtime/wiring.md` to
the state directory's `wiring.md` if it is missing. Continue with items 2–4
below, copying `reviewer-engines.md` only if it is missing. Record bootstrap
output and the installed version in the wiring doc.

1. **Manual fallback:** create the state dir and files if bootstrap was not used:

   ```bash
   mkdir -p <state-dir>/<owner>__<repo>/claims <state-dir>/<owner>__<repo>/locks
   : > <state-dir>/<owner>__<repo>/locks/merge.lock
   cp crew.toml <state-dir>/<owner>__<repo>/crew.toml
   cp <path-to-this-repo>/templates/runtimes/grok-bot/wiring.md <state-dir>/<owner>__<repo>/wiring.md
   cp <path-to-this-repo>/templates/runtimes/grok-bot/reviewer-engines.md <state-dir>/<owner>__<repo>/reviewer-engines.md
   ls -la <state-dir>/<owner>__<repo>/ <state-dir>/<owner>__<repo>/claims
   ```

2. Fill in `wiring.md` from [../templates/runtimes/grok-bot/wiring.md](../../templates/runtimes/grok-bot/wiring.md):
   section 0 from steps 1 to 5 above, section 1 from the identities, section 2
   from [Step 7](../runbook-new-repo.md#step-7-listener-wiring-per-bot), section 4 from the choices in
   step 4. Start from the deployed or manually rendered `runtime/wiring.md`,
   with the profile values already in. Mark every item `planned`, then `applied` or `live` with a date as
   you go. Keep it the one place that lists what is installed.

3. Copy the template, `reviewer-engines.md`, and fill `Updated` plus the
   allowed engine set (private repos: Claude Code or Codex only). Only the
   reviewer bot's main chat edits it afterwards
   ([reviewer-engines.md](../../templates/runtimes/grok-bot/reviewer-engines.md)).

4. Install the README seed. Copy [../templates/product-readme.md](../../templates/product-readme.md)
   into the repo root `README.md` and fill every section, or verify the
   existing README already has problem, what it is, how to run / use, how the
   crew works and status. Record which in the wiring doc. A product repo
   without such a README fails [protocol safety](../protocol.md#8-safety).

### Filled-in wiring.md (derived from the template)

This is what the doc looks like after steps 1 to 6, with placeholders still in
place for your values. A real, dated one is in
[../examples/agentconnect/wiring-summary.md](../../examples/agentconnect/wiring-summary.md).

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
`<out-dir>/runtime/` ([Step 0](../runbook-new-repo.md#step-0-write-validate-and-render-the-profile)),
or from the template file with every install-time placeholder replaced by hand
(the hand-fill fallback). How a routine is created is platform-specific; the
templates give the trigger JSON and prompt text
([../templates/README.md](../../templates/README.md)).

Before choosing profile knobs, read the Grok Bot
[cross-runtime limits](../runtimes/grok-bot.md#cross-runtime-limits): keep
`lighter_lane = "docs"`; review is CI-first; trains are manual and immediate.
The direct lone-PR waiver, runner, scheduler, reap and triage timer are
tmux-only.

The templates carry the merge-up rule
([#20](https://github.com/mw-ding/eng-crew/issues/20)): a clean merge-up after
APPROVE gets a formal merge-up re-approve at the new head with the same round
number; after CHANGES, a COMMENT ack with no round and no verdict; a behavior-
or content-changing resolution gets a normal round; and the synthesizer gate
never accepts a `pass=ack`. See
[reviewer-v2-watch.md](../../templates/runtimes/grok-bot/reviewer-v2-watch.md) and
[synthesizer.md](../../templates/runtimes/grok-bot/synthesizer.md). No override is needed when
filling V2 and S1.

Rules that apply to all:

- Each event has exactly one consuming role. Only the steering dispatcher
  holds `pr-comment` and `inline-review-comment`; nobody holds
  `review-commented`.
- **A routine run cannot create or delete routines.** A wake that needs a
  per-PR watch hands the request to its parent bot turn, which creates it
  ([routine limits](../../templates/README.md#routine-limits)).
- Every per-PR watch lists `pr-merged` and `pr-closed`, and deletes itself
  after that terminal wake.
- A single watch covers only a few repos (4 on the pilot platform); this matters
  only for repo-wide forwarding across many repos.
- Every wake costs a full bot turn. Keep triggers tight.

| Bot | Standing routines (repo-wide) | Per-PR watches | Template files |
|---|---|---|---|
| `<CoordinatorBot>` | A1 after merge; A2 steering dispatcher; A3 stuck-PR sweeper | None by default. Optional comment-event watch on one external PR, created by the coordinator's parent turn when the user wants to steer it | [coordinator-after-merge.md](../../templates/runtimes/grok-bot/coordinator-after-merge.md), [coordinator-steering-dispatcher.md](../../templates/runtimes/grok-bot/coordinator-steering-dispatcher.md), [coordinator-stuck-pr-sweeper.md](../../templates/runtimes/grok-bot/coordinator-stuck-pr-sweeper.md) |
| `<BuilderBot>` | B1 build intake (`issue-assigned`) | B2, created by `<BuilderBot>`'s parent turn right after its worker opens PR `<n>` | [builder-b1.md](../../templates/runtimes/grok-bot/builder-b1.md), [builder-b2.md](../../templates/runtimes/grok-bot/builder-b2.md) |
| `<ReviewerBot>` | V1 PR intake (`pr-opened`) | V2, created by `<ReviewerBot>`'s parent turn after V1 acks PR `<n>` | [reviewer-validator.md](../../templates/runtimes/grok-bot/reviewer-validator.md), [reviewer-v2-watch.md](../../templates/runtimes/grok-bot/reviewer-v2-watch.md), [reviewer-engines.md](../../templates/runtimes/grok-bot/reviewer-engines.md) |
| `<SynthesizerBot>` | S1 merge on approval (`review-approved`) | None | [synthesizer.md](../../templates/runtimes/grok-bot/synthesizer.md) |
| Researcher | None | None | None |

Who creates what, in order, for one PR:

| When | Created by | Routine |
|---|---|---|
| Once, at install | Each bot's owner | B1, V1, S1, A1, A2, A3 |
| After the PR opens | `<BuilderBot>` parent turn | B2 for PR `<n>`, then verified (lists routines, checks the four events, writes the routine folder id to `watches/pr-<n>.b2`, posts the full-SHA `pass=watch` marker). B1 only requests this hand-off. Lighter-lane PRs skip B2 ([protocol §6](../protocol.md#6-duties-on-wake-all-roles)) |
| After V1 acks the PR | `<ReviewerBot>` parent turn | V2 for PR `<n>` |
| On `pr-merged` or `pr-closed` | The watch itself | Deletes itself (B2, V2) |
