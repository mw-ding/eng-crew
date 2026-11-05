# Routine and listener templates

One file per routine, each with a `json` trigger block and a prompt block.
Copy a template onto the bot, replace every placeholder, and keep the wiring
doc ([wiring.md](runtimes/grok-bot/wiring.md)) in sync. These are templates only: nothing here
creates or changes a live routine. For the roles and markers they rely on, see
[../docs/architecture.md](../docs/architecture.md) and the
[docs index](../docs/README.md). A filled-in example is in
[../examples/agentconnect/](../examples/agentconnect/README.md).

## Files

Two trees. Runtime-neutral (core) templates stay at the top of `templates/`,
so their paths and the scripts that read them are unchanged. Templates bound
to one runtime live under `templates/runtimes/<runtime>/`:
[Grok Bot](../docs/runtimes/grok-bot.md), [tmux](../docs/runtimes/tmux.md)
and the proposed [session](../docs/runtimes/session.md) binding. The `crew:needs-mirror` path rule
keys on the `templates/` prefix, so it covers both trees.

### Core (runtime-neutral)

| File | Purpose | Owner |
|---|---|---|
| [flavor-suggestion-issue.md](flavor-suggestion-issue.md) | Owner-decided flavor suggestion; never auto-applied | `<CoordinatorBot>` |
| [handoff-manifest.md](handoff-manifest.md) | Runtime handoff `offered` post that `crew handoff manifest` fills ([handoff](../docs/handoff.md#manifest)) | `<CoordinatorBot>` |
| [intake-candidate.md](intake-candidate.md) | Self-improve intake candidate card (issue body) | `<CoordinatorBot>` |
| [metrics-regression-issue.md](metrics-regression-issue.md) | Issue body for the metrics gate (`harness: latency/quality regression`) | `<CoordinatorBot>` |
| [owner-return-brief.md](owner-return-brief.md) | Standalone return brief for recorded owner away mode | `<CoordinatorBot>` |
| [product-readme.md](product-readme.md) | Seed `README.md` for a product or prove-it repo (problem, what it is, how to run, how the crew works, status); not a routine | `<CoordinatorBot>`, `<BuilderBot>` |
| [evidence/README.md](evidence/README.md) | Evidence adapters index: [cli-exit-stdout.md](evidence/cli-exit-stdout.md), [web-screenshot.md](evidence/web-screenshot.md) | `<BuilderBot>`, `<ReviewerBot>` |
| [step-summary.md](step-summary.md) | `summary.md` skeleton for a builder run (see [observe](../docs/observe.md)); not a routine | `<BuilderBot>` |
| [triage-flavor.md](triage-flavor.md) | Issue rigor record, default and reason for lowering | `<CoordinatorBot>` |

### Grok Bot runtime (`runtimes/grok-bot/`)

| File | Routines | Owner |
|---|---|---|
| [coordinator-steering-dispatcher.md](runtimes/grok-bot/coordinator-steering-dispatcher.md) | Steering dispatcher | `<CoordinatorBot>` |
| [coordinator-after-merge.md](runtimes/grok-bot/coordinator-after-merge.md) | After merge (`pr-merged`, `ci-failed` on `<default-branch>`) | `<CoordinatorBot>` |
| [coordinator-stuck-pr-sweeper.md](runtimes/grok-bot/coordinator-stuck-pr-sweeper.md) | Stuck-PR sweeper (schedule) | `<CoordinatorBot>` |
| [builder-b1.md](runtimes/grok-bot/builder-b1.md) | B1 build intake (`issue-assigned`) | `<BuilderBot>` |
| [builder-b2.md](runtimes/grok-bot/builder-b2.md) | B2 per-PR watch | `<BuilderBot>` |
| [reviewer-validator.md](runtimes/grok-bot/reviewer-validator.md) | V1 PR intake (`pr-opened`) | `<ReviewerBot>` |
| [reviewer-v2-watch.md](runtimes/grok-bot/reviewer-v2-watch.md) | V2 per-PR watch | `<ReviewerBot>` |
| [reviewer-engines.md](runtimes/grok-bot/reviewer-engines.md) | Reviewer engine choice (state file) | `<ReviewerBot>` |
| [synthesizer.md](runtimes/grok-bot/synthesizer.md) | S1 `review-approved` | `<SynthesizerBot>` |
| [researcher.md](runtimes/grok-bot/researcher.md) | Researcher worker brief (no routine; wiring section 2e) | `<CoordinatorBot>` |
| [wiring.md](runtimes/grok-bot/wiring.md) | Per-repo wiring doc template | all |

Grok Bot also renders `skills/eng-pr-pipeline/SKILL.md` and
`skills/eng-crew-roles/SKILL.md` beneath `runtime/`. These inputs include
`docs/protocol.md` and `docs/roles.md` from the running bundle, respectively,
with skill frontmatter. The include directives are restricted to those two
reviewed docs. Their illustrative placeholders remain literal; relative
Markdown links point into `paths.eng_crew`. Deploy the whole render to
`paths.live_dir` so the existing render-vs-live drift check covers skills
and routines together. Box skill installation uses these rendered files;
routine creation remains a human step.

### tmux runtime (`runtimes/tmux/`)

Role briefs for the [tmux runtime](../docs/runtimes/tmux.md), rendered from
[profiles/tmux.toml](../profiles/tmux.toml) and read by `crew up` /
`crew spawn`; golden files in `scripts/fixtures/render/tmux/`.

Builder and solo briefs include `docs/roles.md#pr-conventions` from the
running bundle. This restricted include keeps the PR and fix contract in one
source; illustrative placeholders remain for the session to fill, and link
labels render as plain text for a portable paste-ready contract.

| File | Brief | Owner |
|---|---|---|
| [coordinator.md](runtimes/tmux/coordinator.md) | Window 0: drain the wake queue, spawn / send / kill, keep the watcher armed | `<CoordinatorBot>` |
| [builder.md](runtimes/tmux/builder.md) | Builder window per issue: build, then fix rounds by inbox with `ack:` | `<BuilderBot>` |
| [solo.md](runtimes/tmux/solo.md) | Paste-ready owner-driven session; shares the builder PR contract and rendered precheck | owner session |
| [reviewer.md](runtimes/tmux/reviewer.md) | One review or validate pass, fresh session, verdict file, `done:`, exit | `<ReviewerBot>` |
| [synthesizer.md](runtimes/tmux/synthesizer.md) | Session window: §7 gate, serial land under `flock` | `<SynthesizerBot>` |
| [researcher.md](runtimes/tmux/researcher.md) | One research request, fresh session: signed finding on the source issue, `done:`, window closed | `<ResearcherBot>` |

### Coordinator session (`runtimes/session/`)

Paste-ready, not rendered: the [session binding](../docs/runtimes/session.md)
is design only, so no profile selects it yet.

| File | Brief | Owner |
|---|---|---|
| [coordinator.md](runtimes/session/coordinator.md) | Hand-started coordinator session: ownership guard (`crew ownership --runtime session`) and the [handoff](../docs/handoff.md) outgoing and incoming steps | `<CoordinatorBot>` |

### Backend command mappings (`backends/`)

| File | Contents |
|---|---|
| [github.toml](backends/github.toml) | The `gh` command per operation, from the [GitHub interface mapping](../docs/backends/github.md#interface-mapping); renderer input for `<op:<concern>.<operation>>` |

## Placeholders

Profile key: the resolved [profile](../docs/profile.md#keys) key the
[renderer](../scripts/README.md#renderer) fills the placeholder from. Run-time
placeholders are filled per task and render as written. An operation
placeholder `<op:<concern>.<operation>>` renders as that operation's command in
`backends/<backend>.toml`, for example [backends/github.toml](backends/github.toml).
A line that starts with `<strategy:merge>` or `<strategy:rebase>` is not a
placeholder: it renders, without that prefix, only when the change backend's
[update strategy](../docs/interfaces.md#rebase-update-from-base) matches
(`merge` when undeclared), so a merge render stays byte-identical.

| Placeholder | Meaning | Profile key |
|---|---|---|
| `<owner>` | GitHub owner of the repo | `repo.owner` |
| `<repo>` | Repo name | `repo.name` |
| `<control-item>` | Repo ownership control issue; `none` preserves legacy operation | `repo.control_item` |
| `<runtime-id>` | Runtime name joined to instance with `@`; absent instance renders `unconfigured` | `runtime.name`, `runtime.instance` |
| `<default-branch>` | The repo's default branch (PR base, merge target, `ciBranch`) | `repo.default_branch` |
| `<author-login>` | Author identity: opens branches and PRs, merges. Shared by coordinator, builder, synthesizer, researcher | `identities.coordinator.gh_user`, `identities.builder.gh_user`, `identities.synthesizer.gh_user`, `identities.researcher.gh_user` (must be equal; the researcher's defaults to the coordinator's) |
| `<reviewer-login>` | Reviewer identity: posts formal verdicts and steering signals. Must differ from `<author-login>` | `identities.reviewer.gh_user` |
| `<user-logins>` | The user's own GitHub logins, used as `userAllowlist` and as the accepted commenters for steering. Expands to one JSON string per login | `identities.owners` |
| `<state-dir>` | Shared state directory on the bot box; per-repo state is `<state-dir>/<owner>__<repo>/` (claims, locks, wiring, sweeper state) | `paths.state_dir` |
| `<CoordinatorBot>` | Name of the coordinator bot (also the steering dispatcher) | `identities.coordinator.name` |
| `<BuilderBot>` | Name of the builder bot | `identities.builder.name` |
| `<ReviewerBot>` | Name of the reviewer-validator bot | `identities.reviewer.name` |
| `<SynthesizerBot>` | Name of the synthesizer bot | `identities.synthesizer.name` |
| `<ResearcherBot>` | Name of the researcher bot | `identities.researcher.name` |
| `<CoordinatorTitle>` | Coordinator persona title | `identities.coordinator.title` |
| `<CoordinatorEmoji>` | Coordinator persona emoji | `identities.coordinator.emoji` |
| `<BuilderTitle>` | Builder persona title | `identities.builder.title` |
| `<BuilderEmoji>` | Builder persona emoji | `identities.builder.emoji` |
| `<ReviewerTitle>` | Reviewer persona title | `identities.reviewer.title` |
| `<ReviewerEmoji>` | Reviewer persona emoji | `identities.reviewer.emoji` |
| `<SynthesizerTitle>` | Synthesizer persona title | `identities.synthesizer.title` |
| `<SynthesizerEmoji>` | Synthesizer persona emoji | `identities.synthesizer.emoji` |
| `<ResearcherTitle>` | Researcher persona title | `identities.researcher.title` |
| `<ResearcherEmoji>` | Researcher persona emoji | `identities.researcher.emoji` |
| `<flavor-name>` | Render baseline name; live item/path resolution still applies | `flavor.name` |
| `<flavor-review>` | Render baseline review; live item/path resolution still applies | `flavor.review` |
| `<flavor-validation>` | Render baseline validation; live item/path resolution still applies | `flavor.validation` |
| `<flavor-evidence>` | Render baseline evidence; live item/path resolution still applies | `flavor.evidence` |
| `<flavor-caps>` | Render baseline caps; live item/path resolution still applies | `flavor.caps` |
| `<flavor-merge>` | Render baseline merge; live item/path resolution still applies | `flavor.merge` |
| `<flavor-builder>` | Render baseline builder; live item/path resolution still applies | `flavor.builder` |
| `<flavor-validation-scope>` | Render baseline validation scope (`repo` or `bounded`); live item/path resolution still applies | `flavor.validation_scope` |
| `<flavor-selfgate-engine>` | Profile self-gate engine (`different` or `same`, default `different`); read only for an express change | `flavor.selfgate_engine` |
| `<precheck-test>` | Configured test command, in backticks; unset renders `` `n/a` `` | `builder.precheck.test` |
| `<precheck-lint>` | Configured lint command, in backticks; unset renders `` `n/a` `` | `builder.precheck.lint` |
| `<reviewed-base-sha>` | Full merge-base SHA pinned when the review starts; reused by validation and final verdict | none (run-time) |
| `<n>` | A PR or issue number. In a trigger it is a JSON number once filled in | none (run-time) |
| `<sha7>` / `<head-sha>` | Short or full 40-character head commit SHA | none (run-time) |
| `<k>` | Verdict round number, starting at 1 | none (run-time) |
| `<pass>` | Review pass name, used in worktree names (for example `review`, `validate`) | none (run-time) |
| `<role>` | Role short name, used in worktree names | none (run-time) |
| `<worktree-root>` | Directory holding per-run worktrees; each run uses its own `<worktree-root>/<n>-<sha7>-<role>-<pass>/` | `paths.worktree_root` |
| `<pass\|changes>` | Verdict value in a marker: `pass` or `changes` | none (run-time) |
| `<cmd>` | A steering command name | none (run-time) |
| `<comment id>` | ID of the PR comment that carried a steering command (`cmd-id` in the marker) | none (run-time) |
| `<note>` | Free-text note after a steering command such as `rework` | none (run-time) |
| `<fallback-engine>` | Second allowed engine for the reviewer fallback (private repos: Claude Code or Codex only) | `engines.fallback_engine` |
| `<tested-update>` | The synthesizer's tested-with-default-branch fix: `update-branch or green train`, or under a `rebase` backend `rebase onto the default branch and upload (no trains)` | `strategy.update_from_base` (resolved from the change backend's pack manifest; `merge` when undeclared) |
| `<planned \| applied \| live>` | Status of a wiring step; pick one and add a date | none (run-time) |
| `<timezone>` | IANA timezone for a schedule trigger | `runtime.timezone` |
| `<toolchain-bin>` | Directory of the repo's required toolchain, put on `PATH` before any commit or push | `paths.toolchain_bin` |
| `<eng-crew>` | Absolute path of the eng-crew checkout; tmux briefs cite `<eng-crew>/docs/` | `paths.eng_crew` |
| `<max-active-milestones>` | Maximum open milestones for new coordinator build dispatch, in milestone order | `runtime.options.max_active_milestones` |
| `<lone-pr-land>` | tmux lone-ready-PR landing policy | `runtime.options.lone_pr_land` |
| `<train-min>`, `<train-window>` | tmux synthesizer batching threshold and maximum wait in seconds | `runtime.options.train_min`, `runtime.options.train_window` |
| `<merge-grant>`, `<hold-label-blocks>` | tmux synthesizer's standing merge grant scope and whether `crew:hold` blocks | `runtime.options.merge_grant`, `runtime.options.hold_label_blocks` |
| `<mirror-deferral>` | tmux synthesizer's recorded standing mirror deferral source and scope | `runtime.options.mirror_deferral` |
| `<parent>` | Number of the parent spec issue | none (run-time) |
| `<date>`, `<reason>` | Date and reason recorded in a state file (for example a quota steer) | none (run-time) |
| `<sweep-id>`, `<outcome>`, `<band>`, `<shadow\|apply>` | A triage sweep's UTC start, a triage record's decision slug, its priority band `P0`–`P3` and the sweep's `triage.mode` ([protocol §4](../docs/protocol.md#4-marker-conventions)) | none (run-time) |
| `<UTC timestamp>` | Time written on a claim file's `heartbeat:` line | none (run-time) |
| `<full-40-char-head-sha>` / `<new-head-sha>` | Full 40-character head SHA in a marker; `<new-head-sha>` is the head after a merge-up | none (run-time) |
| `<harness>` | Harness actually used by the authoring session, including fallback | none (run-time) |
| `<pr>`, `<engine>`, `<model>`, `<effort>` | PR number of an evidence path; engine, model and effort that wrote a round ([roles](../docs/roles.md)) | none (run-time) |
| `<worktree>`, `<run-id>`, `<file>` | A run's worktree path, step-summary run ID or CI run ID, and a file path | none (run-time) |
| `<run-url>` | Default-branch CI run URL in a direct-land blocker | none (run-time) |
| `<gate>` | Issue number a coordinator hold-until note waits on | none (run-time) |
| `<branch>`, `<t>`, `<M>`, `<login>`, `<tag>`, `<version>` | Command arguments in [backends/github.toml](backends/github.toml): branch, title, milestone, login, state tag, release version | none (run-time) |
| `<project>`, `<url>`, `<id>`, `<item>`, `<status-field>`, `<option>` | Project board arguments in [backends/github.toml](backends/github.toml) | none (run-time) |
| `<APPROVE\|REQUEST_CHANGES>` | Formal verdict event in [backends/github.toml](backends/github.toml) | none (run-time) |

Quoted placeholders such as `"<n>"` in JSON blocks keep the template valid
JSON. Replace the whole quoted string with a number when filling it in.

## Event to consuming role

Grok Bot runtime: see
[wake wiring](../docs/runtimes/grok-bot.md#wake-wiring-event-to-consuming-role)
and [lighter-lane routing](../docs/runtimes/grok-bot.md#lighter-lane-routing).

## Open items

None.

## Routine limits

Grok Bot runtime: see [routine limits](../docs/runtimes/grok-bot.md#routine-limits).

## Credentials

Templates refer to credentials only by mechanism, for example
`GH_TOKEN=$(gh auth token --user <author-login>)`. Never paste a token, key or
header into a template or a wiring doc.
