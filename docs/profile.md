# Profile (`crew.toml`)

One install-time file picks the runtime, a backend per concern, identities,
engines and paths for one repo (portable eng-crew, roadmap 13.10,
[#122](https://github.com/mw-ding/eng-crew/issues/122);
[portable spec P4](specs/portable.md#2-requirements)). It replaces the
hand-filled placeholders of the [templates](../templates/README.md#placeholders)
and the per-repo [wiring doc](../templates/runtimes/grok-bot/wiring.md).
`scripts/crew-config.py validate <file>` rejects a bad profile before anything
renders ([scripts](../scripts/README.md#profile-validator)).

This page adds no rule, gate, cap, marker field or label; the
[protocol](protocol.md) owns them. `validate` checks one complete file;
`resolve` merges the config layers (13.11,
[#123](https://github.com/mw-ding/eng-crew/issues/123); see
[Layers and precedence](#layers-and-precedence)) on top of the
[default profile](../profiles/default.toml) (13.12,
[#124](https://github.com/mw-ding/eng-crew/issues/124)).

## Format

[TOML](https://toml.io/en/v1.0.0), read with Python's stdlib `tomllib`
(3.11+). Every table and key below is closed: an unknown key fails. A key
marked *required* has no default. Values name identities by mechanism only
(a login, never a token): any string that matches a
[secret pattern](../scripts/README.md#what-it-checks) of `check-repo.py`
fails, unless written as a placeholder such as `<token>`.

## Example

```toml
[repo]
owner = "<owner>"
name = "<repo>"
default_branch = "main"

[runtime]
name = "tmux"
options = { builders = 5, reviewers = 2 }

[backends.change]
name = "github"
[backends.review]
name = "github"
capabilities = { post-verdict = "emulated (COMMENT-review verdict + recorded owner merge-ok)" }
[backends.tracker]
name = "github"
[backends.state-tags]
name = "github"
[backends.markers]
name = "github"
[backends.ci]
name = "github"
[backends.events]
name = "github"
[backends.owner-channel]
name = "github"

[identities]
owners = ["<user-login>"]
coordinator = { gh_user = "<author-login>" }
builder = { gh_user = "<author-login>" }
reviewer = { gh_user = "<author-login>" }
synthesizer = { gh_user = "<author-login>" }

[engines]
coordinator = "claude-code"
trivial = { order = ["claude-code/sonnet", "codex/gpt-6.1-sol"] }
default = { order = ["codex/gpt-6.1-sol", "claude-code/sonnet"] }
deep = { order = ["codex/gpt-6.1-sol", "claude-code/sonnet"], effort = "high" }

[paths]
state_dir = "<state-dir>"
worktree_root = "<worktree-root>"
```

This example is a single-identity profile (reviewer = author), so it
declares the review emulation of
[interfaces: Single-identity profile](interfaces.md#single-identity-profile).

## Keys

### `[flavor]`

Optional named rigor configuration; the [flavor schema](flavors.md#profile-schema)
defines `name`, `goal`, custom compositions and class declarations. The validator
accepts `thorough`, `standard`, `fast` and `solo`; the solo lane uses the
`crew:solo` item label for builder routing.
`resolve` supplies an unset name as `standard` with `core (unset: flagged)`
provenance. Custom tables merge by key; class arrays replace as a whole.
Schema validation does not activate runtime gate modes or precheck defaults:
those integrations remain the flavor design's follow-ups A and B. Existing
`builder.precheck.enabled` and the recorded `runtime.options.merge_grant`
continue to govern runtime behavior until that integration.

### `[repo]`

| Key | Type | Default | Replaces |
|---|---|---|---|
| `owner` | string | *required* | `<owner>` |
| `name` | string | *required* | `<repo>` |
| `default_branch` | string | `"main"` | `<default-branch>` |
| `control_item` | positive integer | none (legacy operation) | ownership control issue ([protocol](protocol.md#ownership-record)) |

### `[runtime]`

Moved to
[Runtime options: `[runtime]`](configuration/runtime-options.md#runtime):
the `name`, `options`, `timezone` and `instance` keys with the `instance`
condition, and the `max_active_milestones` coordinator option both runtimes
accept, with its priority, in-flight and default behavior. The `tmux`
options with their presence/away caps, the standing and render-time `notes`
and the pack render overlay moved to
[Runtime options: `tmux` options](configuration/runtime-options.md#tmux-options).
The `tmux` launch topology (`[runtime.options.launch]`) with its
absent-table fallback, keys and example moved to
[Runtime options: Launch topology](configuration/runtime-options.md#launch-topology).

### `[builder.precheck]`

Optional pre-review check settings, supplied by the project or an org profile.
Tables merge by key; project values override org values.

| Key | Type | Default | Meaning |
|---|---|---|---|
| `enabled` | boolean | `false` | Include the ordered pre-review steps in the builder brief |
| `lint` | string | none | Shell command for lint / format |
| `test` | string | none | Shell command for tests / build |
| `docs` | string | none | Optional shell command for docs checks |
| `max_fix_attempts` | positive integer | `2` | Maximum fixes per failing command, rerunning after each |

When enabled, the renderer adds the [pre-review steps](protocol.md#builder-pre-review-check)
to the core builder brief and the runtime's build intake brief. Missing, empty
or whitespace-only commands render as `n/a`, never `pass`; required docs and
changelog updates still apply. When disabled or omitted, the builder brief
and existing builder duties are unchanged. No merge gate is added.

```toml
[builder.precheck]
enabled = true
lint = "python3 scripts/check-repo.py"
test = "python3 scripts/test-crew-config.py"
max_fix_attempts = 2
```

### `[sensitive]`

Optional `paths`: an array of repo-relative globs extending the mandatory
defaults; `[]` adds none. Layers replace this array; defaults always remain.
`**` crosses `/`; `*` and `?` stay in one segment; matching is case-sensitive.
Empty patterns, absolute paths and `..` segments are invalid.

Defaults: `.github/workflows/**`, and root or nested directories named `auth`,
`secrets`, `permissions`, `access-control`, `migrations` or `deletions`. Add the
project's other security/irreversible paths (including files outside these
directories). For eng-crew, add `docs/protocol.md`, `docs/verification.md`,
`docs/flavors.md` and `scripts/crew-config.py` to protect its gate contract.

```toml
[sensitive]
paths = ["infra/iam/**", "scripts/drop-*.py"]
```

Run `python3 scripts/crew-config.py sensitive --project crew.toml` with full
diff paths on stdin. JSON output names `label` (`crew:sensitive` or `null`)
and `matches` (path → matching rules); exit 1 means invalid configuration,
never a non-sensitive result. Label duties and the owner override are in
[the protocol](protocol.md#sensitive-class).

### `[backends.<concern>]`

One table per concern of [interfaces](interfaces.md#concerns). Eight are
*required*: `change`, `review`, `tracker`, `state-tags`, `markers`, `ci`,
`events`, `owner-channel`. `release` is optional; a profile with a
[`[release]`](#release) table needs it. Any other concern fails.

| Key | Type | Default | Replaces |
|---|---|---|---|
| `name` | string: `github` ([backend](backends/github.md)) or the explicitly supplied external manifest's `pack.name` | *required* | none (was implicit: GitHub) |
| `capabilities` | table: operation → `supported`, `unsupported` or `emulated (<how>)` | `{}` | none |

`capabilities` carries the
[capability declaration](interfaces.md#capability-declaration); an
undeclared operation counts as `unsupported` there. Operation keys per
concern, in the interfaces order:

| Concern | Operation keys |
|---|---|
| `change` | `open`, `push`, `read-head`, `read-diff-paths`, `update-from-base`, `land`, `close` |
| `review` | `post-verdict`, `post-narrative`, `list-verdicts`, `request-rereview` |
| `tracker` | `create-item`, `assign`, `link`, `milestone`, `board-status`, `list-items`, `label`, `comment`, `close-item` |
| `state-tags` | `set-clear-read` |
| `markers` | `write`, `read`, `write-item`, `read-item` |
| `ci` | `check-status`, `failing-jobs` |
| `events` | `subscribe-or-poll` |
| `owner-channel` | `ask`, `notify` |
| `release` | `cut`, `approve-check`, `record-release`, `notify` |

For tmux, `owner-channel` also accepts `name = "slack"`. Only `notify`
uses Slack; `ask` remains a recorded GitHub ask. No other concern accepts
Slack. Configure the secret by environment variable name, never its value:

```toml
[backends.owner-channel]
name = "slack"
[runtime.options]
slack_webhook_env = "CREW_SLACK_WEBHOOK_URL"
slack_digest_interval = 3600
```

Export the webhook in the launching environment before `crew up`; do not
put it in a profile, command argument, run record or log. The
[tmux notification binding](runtimes/tmux.md#slack-progress-notifications)
describes events, retries, digests and the return brief.

### `[release]`

Optional: how the project cuts and records releases through the
[release operations](release.md#release-operations)
([#585](https://github.com/mw-ding/eng-crew/issues/585)). Without the table
nothing changes; eng-crew's own release on GitHub needs none, since every
default below is today's behaviour.

| Key | Type | Default | Meaning |
|---|---|---|---|
| `changelog` | string | `"CHANGELOG.md"` | CHANGELOG path, relative to the profile |
| `fragments` | string | `"changes/unreleased"` | Per-change fragment directory, relative to the profile |
| `versioning` | string: `semver` | `"semver"` | [Versioning](deliverables.md#versioning) scheme for version sections |
| `release_id` | string: `tag` or `commit` | `"tag"` | What `release.record-release` writes: a tag, or the full 40-character hash of the landed cut commit ([commit release id](release.md#commit-release-id)) |

```toml
[release]
changelog = "docs/HISTORY.md"
fragments = "notes/next"
release_id = "commit"
```

With the table, `resolve` requires `backends.release` with
`approve-check` and `record-release` kept (not `unsupported` or undeclared);
otherwise the profile is unsupported for release
([release rule](interfaces.md#capability-declaration)).
`changelog-cut.py --project crew.toml` reads `changelog` and `fragments`;
its flags override them.

### `[triage]`

Optional: the [always-on triage](triage.md) sweep
([#748](https://github.com/mw-ding/eng-crew/issues/748)). Off by default.
When enabled, `crew watch` starts a fresh researcher session with
`crew spawn researcher --sweep` every `interval_hours`, at once when the
crew wakes with a sweep overdue, and skips the slot when
`<state-dir>/<owner>__<repo>/triage/queue.json` lists no items (no unplaced
issue and no owner reply). The timer costs no model turn; its last slot is
in `triage/sweep.json` ([crew watch](runtimes/tmux.md#crew-watch)).

| Key | Type | Default | Meaning |
|---|---|---|---|
| `enabled` | boolean | `false` | Run the sweep timer |
| `interval_hours` | integer, at least 1 | `6` | Hours between sweep slots |
| `repos` | list of `owner/name` strings (non-empty) | the project's `repo.owner/repo.name` | Tracker repos a sweep reads |
| `rules` | string: file path | none (built-in defaults) | The owner's class rules file (label maps, P0 signals, cooldowns); Riley never writes it |
| `mode` | string: `shadow` or `apply` | `"shadow"` | `shadow` writes records and proposals only; the owner sets `apply` after [calibration](triage.md#shadow-mode-and-calibration) |

### `[identities]`

| Key | Type | Default | Replaces |
|---|---|---|---|
| `owners` | list of strings (non-empty) | *required* | `<user-logins>` |
| `coordinator.gh_user` | string | *required* | `<author-login>` |
| `builder.gh_user` | string | *required* | `<author-login>` |
| `synthesizer.gh_user` | string | *required* | `<author-login>` |
| `reviewer.gh_user` | string | *required* | `<reviewer-login>` |
| `researcher` | table: `gh_user`, `name`, `title`, `emoji` | optional; `gh_user` resolves to `coordinator.gh_user`, then `Riley` / `Researcher` / `🔬` | the [researcher](roles.md#researcher-riley)'s author identity: `<author-login>`, `<ResearcherBot>`, `<ResearcherTitle>`, `<ResearcherEmoji>` |
| `<role>.name` | string: role display name, also the tmux window name | `Ash` / `Builder` / `Reviewer` / `Synthesizer` | `<CoordinatorBot>`, `<BuilderBot>`, `<ReviewerBot>`, `<SynthesizerBot>` |
| `<role>.title` | string: neutral role title | `Coordinator` / `Builder` / `Reviewer-validator` / `Synthesizer` | `<CoordinatorTitle>`, `<BuilderTitle>`, `<ReviewerTitle>`, `<SynthesizerTitle>` |
| `<role>.emoji` | string: signature emoji | `🔥` / `🛠️` / `🔎` / `🔀` | `<CoordinatorEmoji>`, `<BuilderEmoji>`, `<ReviewerEmoji>`, `<SynthesizerEmoji>` |

Every role signs authored posts and owner-facing replies as
`— <emoji> <name> (<title>) · <harness> · <model actually used>`.
Name, title and emoji resolve from the profile; harness and model are filled
at run time by the authoring session, including fallback. Engine attribution
still records effort; signatures change no marker or gate.

`gh_user` is the only mechanism today: a GitHub login whose token is derived
at use, `GH_TOKEN=$(gh auth token --user <login>)` (on tmux via
`CREW_IDENTITY`, [Q5](runtimes/tmux.md#q5-identities)). A reviewer equal to
the author is the single-identity profile; `validate` allows it.

### `[engines]`

| Key | Type | Default | Replaces |
|---|---|---|---|
| `coordinator` | string: `claude-code`, `codex`, `pi` or `cursor` | `"claude-code"` | none ([tmux Q3](runtimes/tmux.md#q3-coordinator-engine)) |
| `fallback_engine` | string: an `<engine>` below | none | `<fallback-engine>` |
| `trivial`, `default`, `deep` | table, *required* each | *required* | the [current routing](roles.md#current-routing) row of that tier |
| `<tier>.order` | list of `<engine>/<model>` strings, first choice first | *required* | `<engine>`, `<model>` |
| `<tier>.effort` | string: `low`, `medium` or `high` | `low` / `medium` / `high` by tier ([tiers](roles.md#tiers)) | `<effort>` |
| `roles.<role>.order` | list of `<engine>/<model>` strings, first choice first; `<role>` is a spawned role (`builder`, `reviewer`, `synthesizer`) | none: the tier's `order` | none ([per-role override](roles.md#per-role-engine-override)) |

`<engine>` is one of `claude-code`, `codex`, `muse`, `opencode`, `pi`, `cursor`
([harness adapters](runtimes/harness-adapters.md)); any other engine
fails. The [hard rules](roles.md#hard-rules) still apply to whatever the order
names. A `[engines.roles]` entry replaces the tier's `order` for that role's
workers at every tier; the tier still sets `effort`, and reviewer independence
still filters the role's order. Role leads keep the `default` tier order. Pi accepts provider-qualified models (for example
`pi/anthropic/claude-sonnet-4-5`) and requires `permission_mode = "bypass"`.

### `[size_budget]`

Optional per-role limits for bootstrap's [self-test](bootstrap.md#q7-self-test)
(#194). Keys are `coordinator`, `builder`, `reviewer` and `synthesizer`;
each is a positive integer, default **16384 bytes** (16 KiB). For example:

```toml
[size_budget]
coordinator = 12288
builder = 8192
```

The limit applies to the path-normalized UTF-8 bytes of each rendered Markdown file for that role:
`briefs/<role>.md` and `runtime/<role>.md` or `runtime/<role>-*.md`.
For this measurement only, every install-time placeholder mapped to `paths.*`
is rendered as the fixed six-byte token `<path>`; other profile values remain
expanded. Install-path length cannot change the result. Deployed files retain
their real paths. Shared installation instructions (`wiring.md`) are excluded. A file exactly
at the limit passes; an oversized file fails the self-test, naming its
render-relative path, path-normalized UTF-8 byte count, role and budget. Missing keys use
the default; org and project overrides follow normal layer precedence.

### `[tools.<name>]`

Optional doctor checks for tools the profile names (#193). `running` and
`installed` are required, nonempty argv arrays for read-only version probes;
doctor runs them without a shell, with a 30-second timeout. The running
probe must query the existing session, rather than launch a fresh copy of
the installed tool. The profile supplies the tool-specific probe.

```toml
[tools.example]
running = ["example-session", "version"]
installed = ["example", "--version"]
pin = "2.10.0"
```

Each probe prints a numeric release version `X.Y.Z` (optional `v` prefix
and surrounding text). Optional `pin` is a minimum `X.Y.Z` or `vX.Y.Z`,
compared numerically. Prerelease/build versions are not supported.
Matching versions at or above the pin print `ok`. A running/installed
mismatch or either version below the pin prints `warn` with a restart or
upgrade hint. Failed or unreadable probes print `warn`; they never count
as a match. Drift warnings do not change doctor's exit code, and `--fix`
never upgrades or restarts tools. With no `[tools]`, no probes run.

### `[paths]`

| Key | Type | Default | Replaces |
|---|---|---|---|
| `state_dir` | string | *required* | `<state-dir>` |
| `worktree_root` | string | *required* | `<worktree-root>` |
| `toolchain_bin` | string | none | `<toolchain-bin>` |
| `live_dir` | string: the deployed live copy, laid out like `crew-render.py --out` | none | none (read by `check-skill-drift.py --project`, #128) |
| `pack` | string: pack directory, absolute or relative to this project file | none | records the org pack for resolution |
| `eng_crew` | string: absolute path of the eng-crew checkout, so briefs cite its docs in any repo | none | `<eng-crew>` |

A key with default "none" may be left out of one file; the
[default profile](../profiles/default.toml) sets them except the optional `pack`.

### `[hosts.<name>]` and `[placement]`

Optional: the host inventory and project affinity of a multi-device tmux
crew (20.2, [#204](https://github.com/mw-ding/eng-crew/issues/204); design in
[multi-device](runtimes/multi-device.md#host-inventory-profile-extension)).
With no `[hosts]` table the crew runs on one machine, as today. A host is
named by its overlay network name only, never by an address, user, port or
credential (spec R1). Keep these tables in the host-local project
`crew.toml` or the org layer, never in eng-crew. They replace no template
placeholder; `validate` checks them, and placement that reads them is
[#207](https://github.com/mw-ding/eng-crew/issues/207).

```toml
[hosts.host-a]
primary = true
capabilities = { os = "macos", arch = "arm64", engines = ["claude-code", "codex"] }
max_runs = 2

[hosts.host-b]
capabilities = { os = "macos", arch = "arm64", devices = ["ios-simulator"], engines = ["codex"] }
max_runs = 1
roles = ["reviewer"]

[placement]
hosts = ["host-a"]

[[placement.rules]]
role = "reviewer"
pass = "validate"
paths = ["ios/**"]
needs = { devices = ["ios-simulator"] }
```

| Key | Type | Default | Meaning |
|---|---|---|---|
| `hosts.<name>` | table; `<name>` is a DNS label (`[a-z0-9-]`, 1–63 characters) | none | The host's overlay network name, also its SSH destination |
| `hosts.<name>.primary` | boolean | `false` | Exactly one host is `true`; it runs the coordinator and synthesizer |
| `hosts.<name>.capabilities.os` | string: `linux` or `macos` | *required* | The host's OS |
| `hosts.<name>.capabilities.arch` | string: `x86_64` or `arm64` | *required* | The host's architecture |
| `hosts.<name>.capabilities.devices` | list from `ios-simulator`, `ios-device`, `android-emulator`, `android-device` | `[]` | Attached devices; a new kind is a schema change |
| `hosts.<name>.forge` | boolean | `true` | `false` marks a [forge-less host](runtimes/multi-device.md#forge-less-hosts-remote-test-runner): runner jobs only, never a role session. It needs no `engines`; `validate` refuses it as the primary, with a non-empty `roles` or in `placement.hosts`. `crew host check` shows its logins check as `n/a`, or `warn` if a forge login is found there |
| `hosts.<name>.capabilities.engines` | list of `<engine>` (non-empty) | *required*; none when `forge = false` | Engines logged in on that host |
| `hosts.<name>.max_runs` | integer ≥ 1 | *required* | This crew's concurrent role runs on that host; its concurrent runner jobs on a forge-less host |
| `hosts.<name>.roles` | list from `builder`, `reviewer` | both | Roles placed there |
| `hosts.<name>.root` | string: path on that host | `~/.crew` | Mirrors, worktrees and host state |
| `hosts.<name>.toolchain_bin` | string: path on that host | none | `<toolchain-bin>` for builders there |
| `placement.hosts` | list of host names (non-empty), preferred first | the primary | Project affinity |
| `placement.rules` | array of tables: `role` and `needs` *required*, `pass` and `paths` optional | `[]` | Capability exceptions; first match wins |

In a rule, `role` is `builder` or `reviewer`, `pass` is one of that role's
`crew spawn` passes (`build`, `fix`; `review`, `validate`), `paths` is a
non-empty list of changed-path globs, and `needs` is a table of `os`, `arch`
and `devices` with the values above.

`validate` also fails on: a host name that is not a DNS label (so an IP
literal, `@` or `:`); zero or several primaries; `[placement]` without
`[hosts]`; a `placement.hosts` entry that names no host; a `roles` entry
other than `builder` or `reviewer` (the coordinator and synthesizer run on
the primary only); a role that no `placement.hosts` host takes; a rule whose
`needs` no host taking its role meets; and `[hosts]` with a runtime other
than `tmux`.

### Pack manifest

`packs/<backend>/manifest.toml` is a backend's own
[capability declaration](interfaces.md#capability-declaration):
`[pack]` with `name` (lowercase letters and digits separated by hyphens), `commands` (the doc holding its
command mapping) and, for a pack outside eng-crew, `eng_crew_version`
([packs](packs.md#version-pin)), and `[capabilities.<concern>]` with every operation key of
that concern, all *required*. `[capabilities.release]` is optional; when present, all four keys are required. A profile's `capabilities` table overrides it; `resolve` folds it in
(see [Layers and precedence](#layers-and-precedence)).
`validate` treats a file with a `[pack]` table as a manifest; today's is
[packs/github/manifest.toml](../packs/github/manifest.toml).

## Validate

Moved to
[Configuration resolution: Validate](configuration/resolution.md#validate):
both `validate` command variants, the `file:key: reason` problem format and
exit codes, the full rejection list, and the `--install` check that rejects
install-time placeholders while allowing run-time ones, including the same
check on the effective profile through `resolve --install`.

## Layers and precedence

Moved to
[Configuration resolution: Layers and precedence](configuration/resolution.md#layers-and-precedence):
the `resolve` command and its four-layer table, the merge rule and its
`identities`, `backends` and `engines` exceptions, the cross-key checks
(unsupported invariant with pack-manifest fill, single identity, integer
limit), and the provenance output, problem format and example.

## Team files

Moved to [Team files](configuration/team-files.md):
[schema and example](configuration/team-files.md#schema-and-example) (the
team file's location and name, the `[team]` tables with the `pack`,
`personas` and `accounts` shorthands, the `[repos.<name>]` allowlist and its
refusals, and an example with two repo sections),
[resolution and the team instance](configuration/team-files.md#resolution-and-team-instance)
(project references, clone location, the shared state root and session, and
`crew up --team`), and the migration below.

### Migration: two `crew.toml` files to one team file

Moved to
[Migration: two `crew.toml` files to one team file](configuration/team-files.md#migration-two-crewtoml-files-to-one-team-file):
the five steps from two `crew.toml` files to one team file, with the
`resolve` comparison and the stop, state-move and start order.
