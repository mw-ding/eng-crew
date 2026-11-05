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
example.
[Step 7: listener wiring per bot](../runbook-new-repo.md#step-7-listener-wiring-per-bot)
remains in the runbook.

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
