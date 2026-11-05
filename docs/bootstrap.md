# Bootstrap (design)

> - **Status:** partly built
> - **Applies to:** tmux; `crew bootstrap`, `crew doctor`, `crew upgrade` and their Claude Code and Codex targets
> - **Current rules:** [protocol](protocol.md); [README install steps](../README.md#install)
> - **Built:** Q1–Q9: entry point, `--version` pin, propose → confirm → record, harness targets, preflight, repo fixers (`scripts/crew-repo.py`), self-test and `--smoke`, upgrade and uninstall (#165, #166, #190–#194); `url` and `mirror` [release sources](#release-sources-design) (#943, #944)
> - **Design only:** the `session` runtime target ([session binding](runtimes/session.md)); the `git` release source and host toolkit (#882); [pack harness pointers](#pack-harness-pointers-design) (#883); the "proposed, not filed yet" rows in [Build issues](#build-issues) were not each re-checked
> - **Last checked:** 2026-11-04 at `217cec5`

How a new environment (a Claude Code or Codex session, a Grok Bot account, a
tmux host) gets eng-crew from one reviewed source, at a pinned version, with
the right profile, and proves the install works before any role does work
(roadmap 17.1, [#144](https://github.com/mw-ding/eng-crew/issues/144);
umbrella [#110](https://github.com/mw-ding/eng-crew/issues/110);
[portable spec P4, P5, P9](specs/portable.md#2-requirements); decision
[#160 row 17](https://github.com/mw-ding/eng-crew/issues/160#issuecomment-6532308283)).

This page adds no rule, gate, cap, marker field or label; the
[protocol](protocol.md) owns them. It is design only; the
[build issues](#build-issues) implement it. It builds on the release bundle
and `SHA256SUMS` ([packaging](deliverables.md#packaging)), the
[README install steps](../README.md#install) and the
[update path](release.md#update-path), and does not redesign them.

## Overview

```text
crew bootstrap --project <project>/crew.toml [--org-profile <pack>/profile.toml]
               [--version vX.Y.Z] [--dry-run] [--yes] [--smoke] [--uninstall]
```

| # | Step | Does | Fails closed when |
|---|---|---|---|
| 1 | Locate | Reads `VERSION` from the bundle it runs from; with `--version`, fetches and verifies that bundle first ([Q2](#q2-source-and-version-pin)) | No `VERSION`; a checksum mismatch; a pre-release where a pin applies |
| 2 | Resolve | Merges the config layers; with no project file, proposes one for the owner to confirm ([Q3](#q3-config-resolution)) | A resolve error; a `paths.*` key it uses is still a placeholder; the pack pin is not this version |
| 3 | Preflight | `crew doctor`, read-only ([Q5](#q5-preflight-checks)) | Any `fail` check |
| 4 | Plan | Renders to a temp dir; prints the diff against the live copy and harness targets, each repo operation and the human steps | `--dry-run` stops here, exit 0 |
| 5 | Apply | On the owner's confirmation (or `--yes`): the doctor fixers ([Q6](#q6-repo-side-setup)), the render deploy and the harness targets ([Q4](#q4-install-targets)) | A target path is a tracked file, or was edited since the last install |
| 6 | Record | Version, install manifest and profile copy ([Q2](#q2-source-and-version-pin)) | none |
| 7 | Self-test | [Q7](#q7-self-test) | Any check fails; the record says `failed` and names the check |

Bootstrap never starts or stops a crew: `crew up` (tmux) or routine creation
(Grok Bot) comes next. It never writes, prints or switches a credential
([Q9](#q9-secrets)).

## Decisions

| # | Question | Choice |
|---|---|---|
| 1 | [Entry point](#q1-entry-point) | `crew bootstrap`, a `crew` subcommand run from an extracted release bundle |
| 2 | [Source and pin](#q2-source-and-version-pin) | Release bundle at a tag, checksum-verified; the tag is recorded in the state dir |
| 3 | [Config](#q3-config-resolution) | The #123 layers in-process; a missing project file is proposed, confirmed and recorded once |
| 4 | [Install targets](#q4-install-targets) | Render once into the state dir; untracked pointers where each harness looks |
| 5 | [Preflight](#q5-preflight-checks) | `crew doctor`: one row per check with a fix hint; fail closed |
| 6 | [Repo setup](#q6-repo-side-setup) | Doctor fixers, `crew:*` namespace only, plan first, `--dry-run` |
| 7 | [Self-test](#q7-self-test) | Validate, render, drift, size budget, pointers; a smoke issue behind `--smoke` |
| 8 | [Lifecycle](#q8-idempotency-upgrade-and-uninstall) | Idempotent re-run; upgrade re-renders, diffs, deploys and reloads; uninstall automates offboarding |
| 9 | [Secrets](#q9-secrets) | Mechanism only |
| 10 | [Existing issues](#q10-relation-to-existing-issues) | #129 becomes bootstrap's manual reference; `crew up` is unchanged |

## Q1. Entry point

| Choice | Alternatives considered |
|---|---|
| `crew bootstrap`: a module `scripts/crew.d/bootstrap.py` of the existing `crew` CLI ([#224](https://github.com/mw-ding/eng-crew/issues/224) layout), run as `<eng-crew>/scripts/crew bootstrap`. The first bundle comes from the README install steps (download, `SHA256SUMS`, extract); later ones from bootstrap itself ([Q8](#q8-idempotency-upgrade-and-uninstall)) | A one-line fetch-and-run (`curl … \| sh`): the repo is private, so a plain fetch gets a 404, and it runs code before any checksum is checked. A separate shell installer: a second language and code path beside stdlib Python. A Claude Code plugin as the installer: one harness only ([packaging](deliverables.md#packaging)) |
| No `--runtime` flag: the resolved `runtime.name` decides, so the profile stays the one record (P4) | A `--runtime` flag: two sources for one fact, which can disagree |
| Runs on the host that runs the roles, from any directory; `--project` names the target clone's `crew.toml` | Only from inside the target repo: a Grok Bot box or a second host ([#158](https://github.com/mw-ding/eng-crew/issues/158)) may not run from a clone |
| A clone of eng-crew works only at an exact tag (`git describe --exact-match`); `--dev` records the full SHA and satisfies no pin | Any commit: the install could not say which version it runs |

Where it writes:

| Location | What | Why there |
|---|---|---|
| `<install-root>/eng-crew-<version>/` (the parent of the running bundle) | Extracted bundles, one per version, never edited | Side by side, so a rollback is a re-point ([rollback](release.md#rollback)) |
| `<state-dir>/<owner>__<repo>/` | `crew.toml` copy, `VERSION`, `install.json`, the `eng-crew` link, `render/`, `claims/`, `locks/`, `inbox/` (tmux also `status/`, `wake/`) | The per-repo state home ([runbook](runbook-new-repo.md#shared-state-dir), [tmux layout](runtimes/tmux.md#layout-and-naming)); outside every checkout; no credentials |
| `paths.live_dir` | The deployed render (Grok Bot), drift-checked | The live copy of #128 |
| `<project>` clone | Untracked harness pointers only ([Q4](#q4-install-targets)), each listed in `.git/info/exclude` | Where harnesses look. Precedent: `crew up` writes `.claude/settings.local.json`; `crew spawn` excludes `.crew/` |
| The repo on GitHub | `crew:*` labels, milestone, Project link ([Q6](#q6-repo-side-setup)) | Runbook Steps 1–3 |
| Home dir | Nothing | A home-dir file is shared by every project on the host |

## Q2. Source and version pin

| Topic | Choice | Alternatives considered |
|---|---|---|
| Source | The bundle `eng-crew-<version>.tar.gz` at a tag: `gh release download vX.Y.Z -R mw-ding/eng-crew` with the host's existing `gh` login, checked against `SHA256SUMS` before extraction. Other sources: `url` and `mirror` per [release sources](#release-sources-design) (#882; `git` and the host toolkit still design) | A `git clone` at the tag: kept only as the maintainer path (the "Before bootstrap" row of the [update path](release.md#update-path)); a clone carries internal paths the bundle leaves out. Tracking `main`: P9 says installs record a tag. A submodule or vendored copy in the product repo: a product commit per upgrade. A package manager: hosting and publishing are out of scope |
| Which tag | The bundle it runs from; `--version vX.Y.Z` for an upgrade. Pre-release tags need `--pre` and never satisfy a pin ([versioning](deliverables.md#versioning)) | Implicit "latest": an unattended major bump, which the update path's Decide step gives to the owner |
| Minimum | The first release whose bundle carries every file the install CLI imports ([#275](https://github.com/mw-ding/eng-crew/issues/275); `v2.0.0` lacks one) | none |
| Record | `<state-dir>/<owner>__<repo>/VERSION` (the bundle's file) and `install.json` (tag, bundle SHA-256, runtime, each target path with its SHA-256, pending human steps, status). The link `<state-dir>/<owner>__<repo>/eng-crew` points at the extracted bundle, and `paths.eng_crew` names the link, so an upgrade never edits `crew.toml`. This is the update path's "next to the live copy": beside it, never inside it | The tag in `crew.toml`: bootstrap would rewrite the owner's file each upgrade (#191 records answers once). `VERSION` inside the live dir: `check-skill-drift.py --project` reports any live file the render does not produce as `EXTRA` |
| Pack pin | An org pack's `pack.eng_crew_version` (the `manifest.toml` beside its profile) must equal the installed tag; else fail closed, with the [version pin](packs.md#version-pin) steps as the hint | Warn and continue: a pack is supported only at its pin |
| Upgrade | Pull only ([update path](release.md#update-path)): see [Q8](#q8-idempotency-upgrade-and-uninstall) | A scheduled auto-update: nothing pushes a version into an environment ([compatibility](deliverables.md#compatibility-promise)) |

## Q3. Config resolution

Bootstrap resolves the four layers of
[profile.md](profile.md#layers-and-precedence) in-process through
`resolve_profile` ([#165](https://github.com/mw-ding/eng-crew/issues/165)),
then runs every `validate` and cross-key check.

| Layer | Source at bootstrap | When missing |
|---|---|---|
| `core` | `crew-config.py` defaults | Always present |
| `default` | `<eng-crew>/profiles/default.toml` in the bundle | The bundle is damaged: `SHA256SUMS` fails first; refuse |
| `org` | `--org-profile <pack>/profile.toml`, later `paths.pack` ([#166](https://github.com/mw-ding/eng-crew/issues/166)); never stored in eng-crew | Not given: skipped (P7: the default profile is complete). Given but unreadable, or its pin is not this version: fail closed |
| `project` | `--project <project>/crew.toml` | Propose, confirm, record ([#191](https://github.com/mw-ding/eng-crew/issues/191)): backends from the clone's git config only (never the network), runtime and engines from `profiles/default.toml` or `profiles/tmux.toml`; the owner confirms or edits; written once where `--project` points and never re-derived. Without a terminal and `--yes`: print the proposal and fail |

A team file ([profile.md](profile.md#team-files), #634) resolves the same way,
with `team` and `repo` layers in place of `project`. Name a repo as
`--project <team file>#<repo>`; the four layers above stay the reference for
a legacy `crew.toml`, which is a team file with one repo. Bootstrap still
proposes and records a per-repo `crew.toml` only. Moving two of them into one
team file follows the [migration note](profile.md#migration-two-crewtoml-files-to-one-team-file).

After resolve, a `paths.*` key that a step uses must not be a placeholder
(the [crew rule](runtimes/tmux.md#usage), #265), and the project file is
copied to the state dir (runbook Step 6). Whether the product repo tracks
`crew.toml` stays the owner's choice.

Alternatives considered: a wizard asking every key (dozens of questions where
the default profile already answers most); bootstrap writing one merged file
(it loses the per-key layer and re-derives answers on each run).

For a missing project file, bootstrap reads `remote.origin.url` with
`git config --local`, recognizes GitHub HTTPS and SSH URLs, and proposes GitHub
for each concern. It never probes the network to detect a binding. An unknown
origin requires an owner-supplied `--proposal FILE`. `--runtime tmux` uses the
tmux example's runtime settings; otherwise the bundle's default runtime applies.
Identities, engines and paths continue to come from the existing config layers;
review and fill their placeholders before installation.

`--dry-run` prints the proposal without recording or installing. At a terminal,
confirm with `y`, or enter an edited TOML file's path and confirm that proposal.
For scripted use, pass `--proposal FILE --yes` to record an edited answer, or
`--yes` to accept the printed proposal. Recording precedes the install checks,
so a failed doctor check leaves the confirmed profile available for setup.
An existing project file is never proposed or rewritten, even when these flags
are supplied again. `--flavor` proposes `standard` by default and records the
choice as `flavor.name` in the profile; an edited proposal can change it.
An edited flavor table without a name retains the flagged `standard` default.
The coordinator records item rigor at triage using the
[triage template](../templates/triage-flavor.md).

## Q4. Install targets

**Implemented for tmux role briefs (#339).** Select pointers explicitly on
the first install; later runs reuse the recorded selection:

```sh
crew bootstrap --project <project>/crew.toml --harness claude-code --harness codex --dry-run
crew bootstrap --project <project>/crew.toml --harness claude-code --harness codex --yes
```

With either selection, bootstrap deploys the preview to the state dir's
`render/`, so every pointer names an existing brief. Claude Code gets three
`.claude/agents/crew-<role>.md` pointers (builder, reviewer, synthesizer),
`.claude/skills/crew-coordinator/SKILL.md`, and the same Stop hook as `crew up`.
Every project target has its own anchored `.git/info/exclude` entry and a
hash in `install.json`. Tracked, unowned, edited or symlinked project targets
are refused before apply; existing unowned local settings need owner
reconciliation first. No tracked `AGENTS.md`, `CLAUDE.md` or home file is
written. Codex gets a printed launch command with the brief pointer and the
adapter's per-process trust override, recorded under `launches` in
`install.json`; it gets no project file. `crew spawn` keeps its existing
per-role launch recipe. Nothing launches during bootstrap.

Without a selection or recorded harnesses, tmux bootstrap retains its
render-preview-only behaviour. Removing targets remains the uninstall
follow-up; changing the selection does not delete previously installed files.
The [single-session binding](runtimes/session.md) is design only: these
pointers install files, and supply no new wake or liveness capability.
Grok Bot's routine render is not a role-brief render and refuses `--harness`.
Pointers a pack declares as data are design only:
[pack harness pointers](#pack-harness-pointers-design) (#883).

Content is rendered once, into the state dir (or `paths.live_dir`); a harness
gets only a pointer at the path it loads natively. One copy means one drift
check (#128) and one size budget
([#194](https://github.com/mw-ding/eng-crew/issues/194)). Each target belongs
to its runtime binding or harness adapter (#120,
[#177](https://github.com/mw-ding/eng-crew/issues/177)); gaps use the
[gap format](runtimes/README.md#gap-declaration) against
[C1–C8](runtimes/README.md#contract).

| Target | Loads from | Bootstrap installs | Never touches | Contract gaps |
|---|---|---|---|---|
| Claude Code (session coordinator, roles as subagents) | Project `.claude/agents/`, `.claude/skills/`, `.claude/settings.local.json` | A `crew-<role>.md` subagent per role whose engine is Claude Code: frontmatter and a one-line body pointing at the rendered brief; a `crew-coordinator` skill pointing at the coordinator brief; the turn-end guard Stop hook, as `crew up` adds it. Each path goes in `.git/info/exclude`. Roles on another engine run as that engine's CLI with the same pointer ([how to run each engine](roles.md#how-to-run-each-engine)) | A tracked `CLAUDE.md`, `AGENTS.md` or `.claude/` file; `~/.claude/` | C1 wake on event: partial, compensated by a background `crew watch` the coordinator re-arms each turn (as tmux `ash` does) and the §6 step 3 sweep; residual risk: no work moves while the session is closed. C5 liveness: partial, compensated by claim heartbeats and the §6 sweep, which restarts `missing` work; residual risk: a hung subagent stays `ambiguous` until the harness returns |
| Codex (session coordinator or role engine) | The launch prompt and `-c` overrides | No project file: the launch line carries the pointer `Read your brief at <path> and follow it.` and the pre-trust override, as `crew up` and `crew spawn` do | A tracked `AGENTS.md`; `~/.codex/` | As a session coordinator, C1 wake on event: partial, compensated by the §6 step 3 sweep on each owner turn; residual risk: work waits for the owner's next turn (the typed wake line needs a session backend, [tmux Q3](runtimes/tmux.md#q3-coordinator-engine), #170). As a role engine: no gap beyond the runtime's |
| Grok Bot | Box skills; one routine per role (trigger JSON and prompt) | The rendered routines and `wiring.md` deployed to `paths.live_dir` and drift-checked (#128); `reviewer-engines.md` in the state dir; `runtime/skills/eng-pr-pipeline/SKILL.md` and `runtime/skills/eng-crew-roles/SKILL.md` generated from the bundle's reviewed docs (#341). Routines are human steps, one per rendered file, created by each bot's parent turn ([routine limits](runtimes/grok-bot.md#routine-limits)) | Existing routines; the box's other skills | As declared in the [binding](runtimes/grok-bot.md#runtime-contract) (C1, C2, C3, C5 partial); no new gap. Install gap: routine creation stays manual (#27) |
| tmux | The `crew up` inputs | Checks the profile and the paths `crew up` uses; creates the state dir layout; adds `.crew/` to `.git/info/exclude`; leaves the render and the Stop hook to `crew up` ([crew up](runtimes/tmux.md#crew-up)) | The tmux server and its sessions | As declared in the [binding](runtimes/tmux.md#runtime-contract) (C1, C8 partial); no new gap |

`runtime.name` accepts `grok-bot` and `tmux` today. The single-session mode
of 2026-10-29 (a Claude Code coordinator with subagent builders and a Codex
reviewer) is described by the proposed [session binding](runtimes/session.md),
including its C1–C9 gaps. The Claude Code and Codex rows above describe
installation only; `session` remains unsupported by the validator and renderer.
The session coordinator's guard needs the #279 marker, since a hand-started session has
no `CREW_ROLE`.

Alternatives considered: the full brief in each harness file (two copies
drift, and every session pays the size twice); editing the product's
`AGENTS.md` or `CLAUDE.md` (a product commit outside the crew's PR flow, read
by every worker); user-level files such as `~/.claude/agents/` (shared by
every project on the host, so a second install overwrites the first);
committing the pointers (couples product history to an eng-crew version).

## Q5. Preflight checks

`crew doctor` ([#190](https://github.com/mw-ding/eng-crew/issues/190)) runs
every check read-only and prints one line each: `ok`, `fail`, `warn` or
`human`, with the fix hint. `human` is a fix only a person can make; those
are listed together at the end. Any `fail` stops bootstrap before it writes
anything; exit 0 only with no `fail`. `--fix` runs the fixer where one exists.

| # | Check | Applies to | Fails when | Fix hint |
|---|---|---|---|---|
| 1 | Python | all | `python3` older than 3.11 | Install Python 3.11+ |
| 2 | Bundle | all | `VERSION` missing; files differ from `SHA256SUMS` at fetch | Download again ([Q2](#q2-source-and-version-pin)) |
| 3 | `gh` identities | all | `gh auth status` lacks a login the profile names, or `gh api user` fails for it | `human`: `gh auth login` as that account; never `gh auth switch` |
| 4 | Token scopes | all | `repo` missing; `project` missing on the identity that runs Project operations ([token scopes](runbook-new-repo.md#token-scopes)) | `human`: the account owner runs `gh auth refresh -h github.com -s project`, or Project operations move to an identity that has it |
| 5 | Repo access | all | The author cannot push; a separate reviewer lacks write | `--fix` sends the invitation; `human`: the reviewer accepts |
| 6 | Engines | all | An engine in `engines.coordinator` or a tier `order` has no working CLI (`--version` fails) | Install it, or drop it from the order |
| 7 | Engine auth | all | An auth variable [roles.md](roles.md#how-to-run-each-engine) names for an engine in the order is unset (checked by name; the value is never read into output) | Export it in the roles' environment |
| 8 | Engine policy | all | A free-credit engine is in an order on a private repo ([hard rules](roles.md#hard-rules)); only one engine family is installed, so the reviewer engine cannot differ (invariant 2) | Edit `[engines]`, or install a second engine |
| 9 | Nested sandbox (found 2026-10-29) | Codex in the profile | A no-op command under Codex's own sandbox fails (seen when nested in a sandboxed agent session: exit 71, `sandbox_apply: Operation not permitted`) while `CREW_SANDBOX_ENV` is unset or not `<NAME>=<value>` | Export `CREW_SANDBOX_ENV=<NAME>=<value>` with the variable the org pack names; `crew up` and `crew spawn` pass it to every window. eng-crew never names it |
| 10 | Harness prompts | tmux, session | A role run would stop on a permission or network prompt for `gh` or `git` ([#269](https://github.com/mw-ding/eng-crew/issues/269), [#288](https://github.com/mw-ding/eng-crew/issues/288), [#293](https://github.com/mw-ding/eng-crew/issues/293)) | `warn` with the issue's workaround until those land |
| 11 | tmux | tmux | `tmux` missing | Install tmux |
| 12 | Codex hook trust | tmux, Codex | The host's Codex config has an untrusted hook ([troubleshooting](runbook-new-repo.md#tmux-troubleshooting)) | `human`: trust it in the host config |
| 13 | Folder trust | Claude Code coordinator | First start in a new project | `human`: answer the dialog once (`crew attach ash --rw` on tmux) |
| 14 | Paths | all | A `paths.*` key in use is a placeholder; `state_dir` or `worktree_root` is inside a checkout or not writable | Set it in `crew.toml` |
| 15 | State dir | all | `claims/`, `locks/merge.lock` or `inbox/` missing (tmux also `status/`, `wake/`) | `--fix` creates them |
| 16 | Labels | all | A `crew:*` label of [runbook Step 1](runbook-new-repo.md#step-1-create-the-crew-labels) is missing or differs; another `crew:*` name exists | Missing: `--fix`. Collision: stop; `human`: decide who owns the namespace ([Step 5](runbook-new-repo.md#step-5-product-safety-checks)) |
| 17 | Milestone and Project | all | No open `M*`; no linked Project with Todo, In Progress, In Review, Done | `--fix` with the `project` scope, else `human` |
| 18 | CI | all | No check ran on recent PRs (`crew poll` wakes the reviewer only on green CI); no push CI on the default branch (`warn`) | `human`: add a PR check ([Step 4](runbook-new-repo.md#step-4-check-ci-and-branch-protection)) |
| 19 | One automation | all | Webhooks or apps that also assign, open, review or merge ([protocol §8](protocol.md#8-safety)) | `human`: decide and record it |
| 20 | Tool drift | all | A tool's running version differs from the installed one, or is below its pin ([#193](https://github.com/mw-ding/eng-crew/issues/193)) | Restart the tool or session; upgrade |
| 21 | Local lint | all | `markdownlint-cli2` or `lychee` absent | `warn`: CI is the gate (#110 gap list) |
| 22 | Handoff ([#639](https://github.com/mw-ding/eng-crew/issues/639)) | all | The control item is set but unreadable (every wake is read-only). `warn` when `repo.control_item` or `runtime.instance` is unset, or the [owning runtime](handoff.md#ownership-record) is another instance, draining, in transit or not yet claimed | Set the keys ([handoff](handoff.md)); fix the markers backend's read access |
| 23 | Triage ([#777](https://github.com/mw-ding/eng-crew/issues/777)) | grok-bot | Never fails. `warn` when `triage.enabled = true`: Grok Bot installs no triage timer, and bootstrap's plan says so; triage stays the coordinator's dispositions | Set `triage.enabled = false` ([triage](triage.md)) |

Alternatives considered: fail-with-hint checks only, the first draft of this
issue (#160 row 17 adopted `--fix` and the human-steps list); checks spread
over each command, as `crew` refuses placeholder paths today (no single
report, and the human steps scatter).

## Q6. Repo-side setup

Repo operations are the doctor's fixers for checks 5, 16 and 17, so one
idempotent code path serves `crew doctor --fix` and bootstrap. Bootstrap
prints every operation as the `gh` command it will run, `--dry-run` stops
there, and apply re-reads live state before each one.

| Operation | Mode |
|---|---|
| The ten `crew:*` labels of runbook Step 1 | Created when missing. A differing `crew:*` label is updated only when `install.json` records this install; otherwise it is a collision and bootstrap stops |
| Current `M*` milestone | Created when none is open, with the owner's confirmed name |
| Project: create, link, Status options | With the `project` scope; else a `human` step |
| Reviewer collaborator (two-identity profiles) | Invitation sent; acceptance is `human` |
| Branch protection level, squash-only merges | `human`: the [Step 4](runbook-new-repo.md#step-4-check-ci-and-branch-protection) table is printed and the choice recorded; never applied by bootstrap |
| Product labels and commands, workflows, webhooks, `.github/` | Never touched |

Alternatives considered: a GitHub App or Action that sets up the repo (needs
install rights and its own identity, #80); applying protection automatically
(level C blocks the owner's own merges).

## Q7. Self-test

Runs after every apply, from deliverables only: the bundle ships no
`scripts/test-*.py`.

| # | Check | Proves | Default |
|---|---|---|---|
| 1 | `crew-config.py resolve --project` (validates the layered result) | The profile is well formed | on |
| 2 | Render every role brief and runtime artifact to a temp dir | No unknown placeholder, missing mapping or unsupported capability (the renderer fails closed) | on |
| 3 | `check-skill-drift.py --project` against the deployed live copy (tmux: `render/`) | The deploy equals the render at this version | on |
| 4 | Path-normalized UTF-8 size per always-loaded file (#194) | Every role file fits the profile budget independently of install-path length | on |
| 5 | Each pointer names an existing rendered file; each target's hash matches `install.json` | Harness targets are wired | on |
| 6 | `crew doctor` again | The fixes took effect | on |
| 7 | Smoke issue: the docs-only issue of [runbook Step 8](runbook-new-repo.md#step-8-first-test-issue), end to end | The live pipeline | off; `--smoke` opens a real issue and PR, spends model turns and needs the crew started |

Implemented by `crew bootstrap`: after every apply, resolves and validates the layered profile (the project
may contain only overrides), then renders all runtime artifacts again in a temporary directory,
checks that all four role briefs exist and every role's rendered Markdown file
fits its [size budget](profile.md#size_budget), compares any deployed render byte for byte,
verifies installed target hashes, and runs doctor read-only again. `install.json`
holds `self_test` results; a failed check sets `status = "failed"` and exits 1.
On a fresh tmux install without selected harnesses, deployment is recorded as
`pending crew up`: bootstrap leaves rendering and hooks to `crew up`. Selected
harnesses deploy the render and verify its files and pointer hashes during this
self-test. The `size_budget` check measures a separate render with all
install-time `paths.*` placeholders replaced by the fixed six-byte `<path>`
token and other profile values expanded. It reports each oversized file and
its path-normalized UTF-8 byte count; deployed paths and hashes are unchanged.

`--smoke` queues the docs-only test issue after these checks pass, labelled
`crew:ready` and assigned to the builder. It requires a running tmux session;
Grok Bot operators must create their routines first (bootstrap cannot probe
routine liveness). Dry-run creates no issue. The install record retains the issue
URL and `queued` status, so repeated installs do not create another smoke issue.
A queueing failure is recorded as `self_test.smoke = "fail"`, with install status
`failed`. Smoke permits the repo's required changelog fragment beside the test doc.
It spends real model turns and creates a real PR through the running crew; a queued
issue is not evidence of a passed pipeline. Follow the runbook's Step 8 checklist
to verify review, checks, merge and close-out. Bootstrap never merges or closes it.

Alternatives considered: running the repo's tests (internal, not in the
bundle, and they prove the source, not this install); the smoke issue on by
default (real GitHub objects and quota on every re-run).

## Q8. Idempotency, upgrade and uninstall

Implemented for tmux: run the new bundle’s `crew upgrade --project FILE
--dry-run`, then repeat with `--yes` after reviewing the diff. `--version`
fetches and verifies the selected bundle through the existing bootstrap path.
Run from a separate operator terminal with dispatch paused. The command waits
for terminal worker status, empty lead handoffs and idle panes before applying;
`--wait-timeout` defaults to 300 seconds and leaves the install untouched on
timeout. Roles restart in their existing windows, retaining worktrees, claims,
inboxes and run metadata; the coordinator restarts last. An unchanged render,
pin, source and project profile writes nothing. Grok Bot routine reload is
still manual; this command requires the tmux binding.

| Case | Behaviour |
|---|---|
| Re-run, nothing changed | Each step compares desired with live state; prints `no changes`, writes nothing, exit 0 |
| Re-run, profile changed | Re-render, show the diff, deploy on confirmation |
| Upgrade ([#192](https://github.com/mw-ding/eng-crew/issues/192)) | `--version vX.Y.Z`: fetch and verify next to the current bundle; resolve and render with it; show the diff (render, harness targets, repo operations); a major needs the owner's OK after the `**Breaking:**` entries; deploy; move the `eng-crew` link; record; then reload running roles, coordinator last, each once its in-flight pass ends (terminal worker status and idle pane) |
| Rollback | Upgrade to the previous tag ([rollback](release.md#rollback)); its bundle is still on disk |
| Hand-edited target | A file whose hash differs from `install.json` is never overwritten: it is listed, and that target waits until the owner restores or removes it |
| Pack pointer changed or removed | Design only: [pack harness pointers](#pack-harness-pointers-design) (#883) |
| Uninstall | `--uninstall [--dry-run]` automates [rollback and offboarding](runbook-new-repo.md#rollback-and-offboarding): add `crew:hold` to open crew PRs and `crew:ready` issues; stop the runtime (`crew down`; Grok Bot routine removal is a `human` step per routine ID in the wiring doc); remove the `install.json` targets whose hash still matches, with their exclude lines; archive the state dir, keeping `wiring.md` and evidence; keep the labels unless `--remove-labels`; leave the Project, the collaborator and protection as `human` steps; record what was removed and kept |

Alternatives considered: upgrading in place over the old bundle (no
rollback without a fresh download); restarting roles at once on upgrade (an
in-flight pass would lose its work); uninstall deleting the labels by
default (it strips them from every issue and PR).

## Q9. Secrets

| Rule | How |
|---|---|
| Identities by login only | `gh_user`; each process derives its token at use, `GH_TOKEN=$(gh auth token --user <login>)` ([tmux Q5](runtimes/tmux.md#q5-identities)) |
| Never writes a token | `validate` rejects token-shaped profile values; `install.json` and pointers are scanned with the same patterns before writing, failing closed |
| Never prints one | Variables are checked by name and `gh` by exit code; no value is echoed or logged |
| Never changes host auth | `gh auth login`, `refresh`, `switch` and `logout` are `human` steps only |
| No org names here | The sandbox variable arrives through `CREW_SANDBOX_ENV`, the pack by path; the [denylist check](packs.md#denylist-check) guards the repo |

Alternative considered: bootstrap writing a per-identity credentials file
for the roles (spec R1 forbids stored tokens, and `gh` already holds them).

## Q10. Relation to existing issues

| Issue | Once bootstrap exists |
|---|---|
| #129 runbook by profile (done) | The manual reference for what bootstrap automates. A docs follow-up leads Step 0 and Step 6 with `crew bootstrap` and keeps the manual steps as the fallback |
| #131 `crew up` (done) | Unchanged: it starts the tmux crew. Bootstrap installs, checks and self-tests; it never starts or stops a crew |
| #27 routine installer (closed) | Still manual: each bot's parent turn creates its routines from bootstrap's rendered files |
| #128, #140 | Bootstrap deploys the render and runs the drift check, replacing hand mirroring; box skills are included in `runtime/skills/` (#341). #140 stays the one-time deployment sync |
| [Update path](release.md#update-path) | Bootstrap implements the Record and Take rows; Learn stays with the coordinator and `crew doctor` |
| #158 `crew host check` (M20) | The same check-and-fix shape as `crew doctor` (#190) |
| #156, M18 flavors | The propose step records `flavor.name`; no flavor means `thorough`, flagged |
| #177–#179 harness adapters | The Claude Code and Codex rows of [Q4](#q4-install-targets) become install fields of each adapter |
| #279 adopt the current agent | An adopted coordinator is installed the same way; its guard marker is #279's |

Alternative considered: folding `crew up` into bootstrap (install and run in
one command, so a restart would re-run every check and a Grok Bot install
would have nothing to start).

## Release sources (design)

**Status: design only** ([#882](https://github.com/mw-ding/eng-crew/issues/882)
slice D). Built so far: slice B1, the `[install]` validator and the shared
verifier and `transport` record in `scripts/crew-install.py`; slice B2
([#944](https://github.com/mw-ding/eng-crew/issues/944)), the `url` and
`mirror` sources in bootstrap and upgrade `--version`, the `transport`
record, upgrade's source check and the doctor rows; slice B3
([#945](https://github.com/mw-ding/eng-crew/issues/945)), the `git` source;
slice B4 (folded into #945), the host toolkit install below. Until slice
B5 lands, host check does not verify the toolkit and `--prune` is absent.
Decisions: Riley's
[#649 ACs §11](https://github.com/mw-ding/eng-crew/issues/649#issuecomment-6643902567)
recommendations, accepted at triage: Git carries a commit-verified source,
not a checksummed bundle (a); "never call `gh`" covers release transport
(b); the primary's install record is the host toolkit pin (c). Install code
stays security-sensitive: each slice keeps the owner's per-change merge-ok.

Hosts that cannot reach GitHub get releases from an internal location. Today
a pack stages each bundle by hand, and nothing proves at use that a host's
toolkit equals the pin. An `[install]` source moves the fetch and its proof
into bootstrap, upgrade and host prepare.

### Declaration

An optional `[install]` table in the project or pack profile. Without it the
source is `github`, and every command, output and record stays as today.
That keeps the change within a minor release.

| Key | Values (default) | Meaning |
|---|---|---|
| `source` | `github` \| `url` \| `mirror` \| `git` (`github`) | Where `--version` fetches a release |
| `location` | string | `url`: a base URL; `mirror`: a local directory; `git`: a remote. Each `url` or `mirror` location holds `eng-crew-<v>.tar.gz` and `SHA256SUMS` per version under `<location>/v<v>/`, the layout of GitHub's release downloads. Refused under `github` |
| `sha256sums_digest` | 64 hex | Optional pin on the SHA-256 of the version's `SHA256SUMS`; `url` and `mirror` only |
| `git_commit` | 40 or 64 hex | The full commit the tag must resolve to; required for `git`, refused otherwise |

```toml
[install]
source = "mirror"
location = "/srv/releases/eng-crew"
sha256sums_digest = "<sha256 of SHA256SUMS>"
```

`url` takes `https`, or `http` only to a loopback host (the test server).
`resolve` refuses a missing `location`, a short or non-hex pin and a key the
source does not use. One pin names one version: `--version` for another tag
under a pinned source fails until the pin is updated with it.

### One verifier

Bootstrap, upgrade and host prepare share one fetch and verify step, the
current `fetch` generalized. For `github`, `url` and `mirror` it:

1. Copies `eng-crew-<v>.tar.gz` and `SHA256SUMS` into a staging directory
   beside the bundles (`gh release download`, an HTTP GET or a file copy).
   Later steps read only the staged copies.
2. With `sha256sums_digest`, refuses a `SHA256SUMS` whose digest differs.
3. Refuses unless `SHA256SUMS` has exactly one entry for the archive and it
   equals the archive's digest: a missing, duplicate or mismatched entry
   fails.
4. Applies the existing member checks (one top directory, no `..`, files
   and directories only), then extracts.
5. Refuses unless `VERSION` equals the tag and `scripts/crew` exists, then
   moves the bundle into place.

Nothing is extracted or run before steps 2 and 3 pass. A failure removes the
staging directory and leaves the previous bundle, link and record untouched.

Without the pin, `SHA256SUMS` comes from the same place as the archive: it
catches corruption and partial copies, not a substituted release. Pin it
when the location is not trusted as much as GitHub.

### Git: commit-verified source

A Git remote carries source, not the release archive, so it is never shown
as a `SHA256SUMS`-checked bundle. Its trust root is `git_commit`:

1. Fetch `refs/tags/v<v>` from `location` into a temporary bare repository.
   No checkout and no hooks run.
2. Refuse unless the tag peels to exactly `git_commit`.
3. Build the bundle from that commit with its own
   `scripts/release-bundle.py`, which runs only after step 2. Apply verifier
   steps 4 and 5 to the result.

The record names the commit; the built archive's digest is kept as
`bundle_sha256`, but a rebuilt archive is not promised byte-identical to the
published one. In a SHA-1 repository the pin is as strong as Git's
collision-detecting SHA-1.

### Record and doctor

`install.json` keeps `source` (the bundle directory) and `bundle_sha256`. A
non-GitHub install adds `transport`:

| Field | `url` / `mirror` | `git` |
|---|---|---|
| `kind`, `location` | as declared | as declared |
| `sha256sums_sha256` | digest of the staged `SHA256SUMS` | none |
| `pinned` | whether `sha256sums_digest` was set | none |
| `commit` | none | the verified commit |

A record without `transport` reads as `github`, so old records stay valid.
Upgrade's `no changes` test also compares `transport` with the profile's
source. When the record is for the running bundle and its kind or location
differs from the profile's, plain `crew upgrade` refuses: that bundle was
not fetched from the new source. `crew upgrade --version <tag>` fetches,
re-verifies and re-records it. `crew doctor` adds an
`install source` row: kind, location and the bundle digest or commit, and
whether `SHA256SUMS` was pinned. A record without `transport` adds no row.

### GitHub calls

Under a non-`github` source, `--version` makes no `gh` call and no
latest-release query. The doctor `version` row reports the installed tag
with `latest not checked (source <kind>)`. Doctor rows 3 to 5 and 16 to 19
and the [repo setup](#q6-repo-side-setup) still use the profile's GitHub
calls. A fully GitHub-free install also needs those routed through backends:
that is a separate item, not part of B1 to B5.

### Host toolkit

The primary's `install.json` is the pin: tag, `transport` and
`bundle_sha256` (or commit). A host never chooses its own version. The
toolkit is active only when the profile has an `[install]` table; without
one, host prepare and check send no pin and behave as before. Host-side
layout under `root`:

| Path | Holds |
|---|---|
| `toolkit/eng-crew-<v>/` | The verified bundle |
| `toolkit/eng-crew-<v>.json` | Its record: tag, transport, bundle digest or commit, SHA-256 of every file |
| `state/<owner>__<repo>/toolkit.json` | The version this project pins on this host |

`crew host prepare` runs the verifier on the host, from the same source (a
`mirror` path must exist on the host), against the primary's pin: the
pinned `SHA256SUMS` digest and bundle digest for `url` and `mirror`, the
commit for `git`, the bundle digest for `github`. It is the optional
`toolkit` field of the `prepare` and `seed` calls; with no release install
on the primary, prepare fails at step `toolkit`. It extracts under `toolkit/.staging-*`, writes the record last, then renames.
An existing version whose record and file hashes match is reused. A version
without a record, or with any mismatch, is moved aside and installed again;
it is never ready in between. The project's remote entrypoint runs from the
pinned toolkit.

[Host readiness](runtimes/multi-device.md#host-readiness) row 2 then fails
when the pinned toolkit is missing, its record differs from the primary's
pin, or a file hash differs: `crew host check` adds a required `toolkit`
row from the `version` call with the pin. Row 7 (project mirror) stays required on its
own. `crew host prepare --prune` removes the toolkit versions and staging
leftovers that no `toolkit.json` on that host names, and lists what it
removed.

### Compatibility

All keys and fields are optional. Without `[install]`, behaviour, output and
`install.json` stay byte-identical. The bundle running `--version` must
already know `[install]` (v5.1.0 or later), so an offline host stages that
first bundle by hand one last time.

### Slices

| Slice | Paths | Adds |
|---|---|---|
| B1 [#943](https://github.com/mw-ding/eng-crew/issues/943) | `scripts/crew-config.py`, `scripts/crew-install.py` (new), `docs/profile.md` | `[install]` schema and refusals; the shared verifier and `transport` record |
| B2 [#944](https://github.com/mw-ding/eng-crew/issues/944) | `scripts/crew.d/bootstrap.py`, `upgrade.py`, `doctor.py` | `url` and `mirror` fetch; no-`gh` transport; upgrade no-op; doctor rows |
| B3 [#945](https://github.com/mw-ding/eng-crew/issues/945) | `scripts/crew-install.py` | `git` source |
| B4 [#946](https://github.com/mw-ding/eng-crew/issues/946) | `scripts/crew.d/host.py`, `scripts/crew-remote.py` | Toolkit install in host prepare |
| B5 [#947](https://github.com/mw-ding/eng-crew/issues/947) | the same | Host check pin and file verification; `--prune` |

Tests across the slices: a mirror directory, a local HTTP server, a local
bare Git repository, missing, duplicate and mismatched entries, a pin
mismatch, unsafe members, a bad `VERSION`, a tampered host toolkit, and a
failed verification that keeps the previous install.

## Pack harness pointers (design)

**Status: design only** ([#883](https://github.com/mw-ding/eng-crew/issues/883)
slice D). Nothing here is active yet. Until slices B1 to B3 land, `--harness`
installs only the [Q4](#q4-install-targets) set and the validator rejects
`pack.harness`. Decisions: Riley's
[#649 ACs §12](https://github.com/mw-ding/eng-crew/issues/649#issuecomment-6643902567),
accepted at triage: project-local targets only, and no executable registry
mode. The Q4 and Q8 safety rules stay the contract; install code stays
security-sensitive, so each slice keeps the owner's per-change merge-ok.

An org's harness sessions also need pointers eng-crew cannot know: how to run
the org's review and tracker tools, where the venue's docs live, extra role or
tool skills. Today a pack ships its own installer script for them, outside
bootstrap's refusals, excludes, hashes and uninstall. A registry makes them
data that bootstrap installs under the same rules as its own pointers.

### Registry

`pack.harness` in the pack's `manifest.toml` names a TOML file in the pack.
Without it, every command, output and record stays as today. Each
`[[pointer]]` entry is one of two shapes:

| Key | File entry | Launch-note entry |
|---|---|---|
| `harness` | required | required: `codex` |
| `target` | required: project-relative path | refused |
| `source` | required: pack-relative file | refused |
| `mode` | `copy` \| `pointer` (`copy`) | refused |
| `launch_note` | refused | required: pack-relative file |

```toml
# <pack>/manifest.toml
[pack]
harness = "harness.toml"

# <pack>/harness.toml
[[pointer]]
harness = "claude-code"
target = ".claude/skills/org-review-tool/SKILL.md"
source = "harness/review-tool.md"
mode = "copy"

[[pointer]]
harness = "codex"
launch_note = "harness/codex-venue.md"
```

`harness` names an adapter with an [install pointer](runtimes/harness-adapters.md#fields)
that bootstrap implements: `claude-code` or `codex` today. An adapter
without one (`pi`, `cursor`, `muse`) or an unknown name is refused.

### Modes

| Mode | Target content |
|---|---|
| `copy` | The source bytes, unchanged. For files a harness needs whole, such as a skill with frontmatter |
| `pointer` | One line, `Read <source> and follow it.`, with the source's absolute path in the pack checkout. One copy, as Q4 prefers |
| launch note | No file. The printed Codex launch prompt gains `Then read <note> and follow it.` per note, in registry order, each after a space following the brief pointer. The note is never inlined into argv |

No mode runs pack code: bootstrap reads sources as data and writes text.

### Checks

`crew-config.py validate <pack>/manifest.toml` and `resolve` check the
registry statically:

- Known keys per shape; `harness` as above; `mode` is `copy` or `pointer`.
- `target` is relative and normalized: no leading `/` or `~`, no `..` or
  `.` component, no `.git` component.
- Targets are unique, and none equals a Q4 built-in target
  (`.claude/agents/crew-<role>.md`, `.claude/skills/crew-coordinator/SKILL.md`,
  `.claude/settings.local.json`).
- `source` and `launch_note` resolve, with symlinks followed, to a regular
  UTF-8 file inside the resolved pack directory.

Bootstrap repeats the source checks at install, then checks every target
with the Q4 rules: it refuses a tracked target, a symlinked target or parent
inside the project, and a target that exists with a hash other than the
recorded one (edited or unowned). It lists every refused target and writes
nothing; there is no partial install. Targets are relative to the project
directory, the one that holds `crew.toml`, as for the built-ins.

### Install, dry-run and record

Only entries whose `harness` is in the selection (`--harness`, or the
recorded `harnesses`) install. Each target is a bootstrap target like the
built-ins: the planned diff, an anchored `/<target>` line in
`.git/info/exclude`, and its SHA-256 under `targets` in `install.json`.
`--dry-run` prints each target's diff, its exclude line and the Codex launch
line with its notes. The launch line is recorded under `launches`, as now.

`install.json` adds one optional field when at least one registry target is
installed: `harness_pointers`, mapping each target path to its pack-relative
source and mode. It tells upgrade which targets the registry owns. With no
registry, or no entry for a selected harness, the field is absent and the
record is byte-identical to today.

### Upgrade and removal

Upgrade plans the registry from the current pack checkout and compares it
with the install. Its `no changes` test also requires each planned target's
content to equal the file, the planned target set to equal the
`harness_pointers` entries of the selected harnesses, and the planned launch lines to equal `launches`. A
changed source, mode, pack path or note therefore re-plans even when the
render and tag are unchanged.

| Case | Behaviour |
|---|---|
| Source or mode changed, target unchanged since install | Rewritten; new hash recorded |
| Target edited since install (hash differs) | Listed as `drift: <target>`; the upgrade writes nothing until the owner restores or removes it (Q8 hand-edited target) |
| Entry removed from the registry, target unchanged | Deleted with its exclude line; dropped from `targets` and `harness_pointers` |
| Entry removed, target edited | Kept and listed as a human step; dropped from the record, so a later entry for it is refused as unowned |
| Harness deselected | As Q4 for the built-ins: its targets stay installed, owned and recorded, and the `no changes` test skips them; uninstall removes them |

Uninstall removes every unchanged target in `targets`, registry ones
included, with its anchored exclude line. Today's uninstall matches exclude
lines without the leading `/` that bootstrap writes, so B3 fixes that match
for all harness targets.

### Compatibility

`pack.harness` and `harness_pointers` are optional; no key, field, command,
marker or exit code is removed or renamed. Without a registry, behaviour,
output and `install.json` stay byte-identical, which keeps the change within
a minor release.

### Slices

| Slice | Paths | Adds |
|---|---|---|
| B1 [#964](https://github.com/mw-ding/eng-crew/issues/964) | `scripts/crew-config.py`, `docs/profile.md` | `pack.harness` and the registry schema; static checks |
| B2 [#965](https://github.com/mw-ding/eng-crew/issues/965) | `scripts/crew.d/bootstrap.py` | Planning, install-time checks, launch notes, excludes, `harness_pointers` |
| B3 [#966](https://github.com/mw-ding/eng-crew/issues/966) | `scripts/crew.d/upgrade.py`, `scripts/crew.d/_bootstrap_uninstall.py` | `no changes` test, drift, removed entries, the anchored exclude match |

Tests across the slices: copy, pointer and launch note; an unimplemented
adapter and an unknown one; a target collision with another entry and with a
built-in; `..`, absolute and home targets; a source escaping the pack by
`..` and by symlink; tracked, edited and symlinked targets; a pack-only
upgrade; a removed entry; uninstall; and a byte-identical `install.json`
without a registry.

## Build issues

| Design part | Issue |
|---|---|
| Preflight checks, `--fix`, human steps ([Q5](#q5-preflight-checks)) | [#190](https://github.com/mw-ding/eng-crew/issues/190) (17.2) |
| Propose → confirm → record ([Q3](#q3-config-resolution)) | [#191](https://github.com/mw-ding/eng-crew/issues/191) (17.3), after #165 |
| Upgrade and reload ([Q8](#q8-idempotency-upgrade-and-uninstall)) | [#192](https://github.com/mw-ding/eng-crew/issues/192) (17.4) |
| Tool drift ([Q5](#q5-preflight-checks) row 20) | [#193](https://github.com/mw-ding/eng-crew/issues/193) (17.5) |
| Size budget ([Q7](#q7-self-test) row 4) | [#194](https://github.com/mw-ding/eng-crew/issues/194) (17.6) |
| `resolve_profile` ([Q3](#q3-config-resolution)) | [#165](https://github.com/mw-ding/eng-crew/issues/165) |
| Pack by path, `paths.pack` ([Q3](#q3-config-resolution)) | [#166](https://github.com/mw-ding/eng-crew/issues/166) |
| `crew bootstrap` core: locate, resolve, doctor, plan, `--dry-run`, record, the `eng-crew` link; `scripts/crew` and `scripts/crew.d/` become runtime `all` in the manifest | proposed, not filed yet |
| Bundle fetch: `--version`, `SHA256SUMS`, side-by-side extract, `--pre`, pack-pin check | proposed, not filed yet |
| Release sources: `url`, `mirror` and `git`; host toolkit ([release sources](#release-sources-design)) | [#882](https://github.com/mw-ding/eng-crew/issues/882) slices B1 to B5 (#943 to #947) |
| Repo fixers: labels, milestone, Project, invitation ([Q6](#q6-repo-side-setup)) | proposed, not filed yet |
| Harness targets: Claude Code files, Codex launch pointer ([Q4](#q4-install-targets)) | proposed, not filed yet |
| Pack harness pointers: registry, copy and pointer targets, Codex launch notes ([pack harness pointers](#pack-harness-pointers-design)) | [#883](https://github.com/mw-ding/eng-crew/issues/883) slices B1 to B3 (#964 to #966) |
| `session` runtime binding (design) | [#340](https://github.com/mw-ding/eng-crew/issues/340) (17.13); [binding](runtimes/session.md), implementation remains follow-up |
| Box-skill render input (Grok Bot) | [#341](https://github.com/mw-ding/eng-crew/issues/341) (17.14) |
| Self-test and `--smoke` ([Q7](#q7-self-test)) | proposed, not filed yet |
| Uninstall ([Q8](#q8-idempotency-upgrade-and-uninstall)) | proposed, not filed yet |
| Runbook leads with `crew bootstrap` ([Q10](#q10-relation-to-existing-issues)) | proposed, not filed yet |
