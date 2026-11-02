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

### `[repo]`

| Key | Type | Default | Replaces |
|---|---|---|---|
| `owner` | string | *required* | `<owner>` |
| `name` | string | *required* | `<repo>` |
| `default_branch` | string | `"main"` | `<default-branch>` |
| `control_item` | positive integer | none (legacy operation) | ownership control issue ([protocol](protocol.md#ownership-record)) |

### `[runtime]`

| Key | Type | Default | Replaces |
|---|---|---|---|
| `name` | string: `grok-bot` or `tmux` ([runtimes](runtimes/README.md)) | *required* | none (was implicit: Grok Bot) |
| `options` | table, keys per runtime below | `{}` | none |
| `timezone` | string (IANA name) | none | `<timezone>` |
| `instance` | string: `[a-z0-9-]`, 1–63 characters | none; required with `control_item` | owner-chosen instance label, never a host name or path |

`grok-bot` takes no options. `tmux` ([binding](runtimes/tmux.md)):

| Option | Type | Default | Replaces |
|---|---|---|---|
| `session` | string | `crew-<owner>-<repo>` | the session name in [Layout and naming](runtimes/tmux.md#layout-and-naming) |
| `builders` | integer | `5` | builder band cap ([Q6](runtimes/tmux.md#q6-concurrency)) |
| `reviewers` | integer | `2` | reviewer pass cap ([Q6](runtimes/tmux.md#q6-concurrency)) |
| `poll_interval` | integer | `60` | seconds between `crew poll` runs ([crew poll](runtimes/tmux.md#crew-poll)) |
| `train_min` | integer, at least 2 | `2` | `<train-min>`: train ready PRs at once at this threshold; below it, wait only if another PR is close to approval, otherwise land alone ([land rules](protocol.md#land-rules-and-merge-trains)) |
| `train_window` | integer, at least 1 | `600` | `<train-window>`: maximum wait in seconds after the first PR becomes ready when another is close to approval; at expiry train two or more ready PRs, or land the single ready PR alone |
| `merge_grant` | string | `"none"` | `<merge-grant>`: the owner's standing merge grant scope for the synthesizer brief, with its source (e.g. `#110 roadmap PRs per #111`); `none` means a recorded owner merge-ok per PR. It gives permission only ([§7](protocol.md#7-merge-gate-synthesizer)) |
| `train_local_checks` | boolean | `false` | Opt in to the local full suite before opening the train PR; `--local` also enables it. Default builds record `local=skipped`. A local pre-check is a future CI-velocity option, not a merge gate; green train CI is still required |
| `mirror_deferral` | string | `"none"` | `<mirror-deferral>`: source and scope of a recorded owner standing mirror deferral (e.g. `#110 roadmap PRs per #140`). The synthesizer checks coverage, excludes live Grok Bot behaviour changes and records use in the merge post; this gives no merge permission ([§7](protocol.md#7-merge-gate-synthesizer)) |
| `hold_label_blocks` | boolean | `true` | `<hold-label-blocks>`: whether `crew:hold` stops the tmux builder, reviewer and synthesizer; `false` treats it as a lane label (#111 roadmap PRs). `crew:escalated` and a coordinator hold-until always stop |
| `permission_mode` | string: `bypass`, `auto` or `safe` | `"bypass"` | none: the role windows' permission flags ([crew spawn](runtimes/tmux.md#crew-spawn), #293). `bypass` lets agents run any command in their worktree without asking; `auto` and `safe` keep the harness's approval checks, which can stop a window on a prompt |

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

One table per concern of [interfaces](interfaces.md#concerns), all eight
*required*: `change`, `review`, `tracker`, `state-tags`, `markers`, `ci`,
`events`, `owner-channel`. Any other concern fails.

| Key | Type | Default | Replaces |
|---|---|---|---|
| `name` | string: `github` ([backend](backends/github.md)) | *required* | none (was implicit: GitHub) |
| `capabilities` | table: operation → `supported`, `unsupported` or `emulated (<how>)` | `{}` | none |

`capabilities` carries the
[capability declaration](interfaces.md#capability-declaration); an
undeclared operation counts as `unsupported` there. Operation keys per
concern, in the interfaces order:

| Concern | Operation keys |
|---|---|
| `change` | `open`, `push`, `read-head`, `read-diff-paths`, `update-from-base`, `land`, `close` |
| `review` | `post-verdict`, `post-narrative`, `list-verdicts`, `request-rereview` |
| `tracker` | `create-item`, `assign`, `link`, `milestone`, `board-status` |
| `state-tags` | `set-clear-read` |
| `markers` | `write`, `read`, `write-item`, `read-item` |
| `ci` | `check-status`, `failing-jobs` |
| `events` | `subscribe-or-poll` |
| `owner-channel` | `ask`, `notify` |

### `[identities]`

| Key | Type | Default | Replaces |
|---|---|---|---|
| `owners` | list of strings (non-empty) | *required* | `<user-logins>` |
| `coordinator.gh_user` | string | *required* | `<author-login>` |
| `builder.gh_user` | string | *required* | `<author-login>` |
| `synthesizer.gh_user` | string | *required* | `<author-login>` |
| `reviewer.gh_user` | string | *required* | `<reviewer-login>` |
| `<role>.name` | string: role display name, also the tmux window name | none | `<CoordinatorBot>`, `<BuilderBot>`, `<ReviewerBot>`, `<SynthesizerBot>` |

`gh_user` is the only mechanism today: a GitHub login whose token is derived
at use, `GH_TOKEN=$(gh auth token --user <login>)` (on tmux via
`CREW_IDENTITY`, [Q5](runtimes/tmux.md#q5-identities)). A reviewer equal to
the author is the single-identity profile; `validate` allows it.

### `[engines]`

| Key | Type | Default | Replaces |
|---|---|---|---|
| `coordinator` | string: `claude-code` or `codex` | `"claude-code"` | none ([tmux Q3](runtimes/tmux.md#q3-coordinator-engine)) |
| `fallback_engine` | string: an `<engine>` below | none | `<fallback-engine>` |
| `trivial`, `default`, `deep` | table, *required* each | *required* | the [current routing](roles.md#current-routing) row of that tier |
| `<tier>.order` | list of `<engine>/<model>` strings, first choice first | *required* | `<engine>`, `<model>` |
| `<tier>.effort` | string: `low`, `medium` or `high` | `low` / `medium` / `high` by tier ([tiers](roles.md#tiers)) | `<effort>` |

`<engine>` is one of `claude-code`, `codex`, `muse`, `opencode`
([how to run each engine](roles.md#how-to-run-each-engine)); any other engine
fails. The [hard rules](roles.md#hard-rules) still apply to whatever the order
names.

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
| `eng_crew` | string: absolute path of the eng-crew checkout, so briefs cite its docs in any repo | none | `<eng-crew>` |

A key with default "none" may be left out of one file; the
[default profile](../profiles/default.toml) sets every one of them.

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
| `hosts.<name>.capabilities.engines` | list of `<engine>` (non-empty) | *required* | Engines logged in on that host |
| `hosts.<name>.max_runs` | integer ≥ 1 | *required* | This crew's concurrent role runs on that host |
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
`[pack]` with `name` (a backend above), `commands` (the doc holding its
command mapping) and, for a pack outside eng-crew, `eng_crew_version`
([packs](packs.md#version-pin)), and `[capabilities.<concern>]` with every operation key of
that concern, all *required*. A profile's `capabilities` table overrides it; `resolve` folds it in
(see [Layers and precedence](#layers-and-precedence)).
`validate` treats a file with a `[pack]` table as a manifest; today's is
[packs/github/manifest.toml](../packs/github/manifest.toml).

## Validate

```sh
python3 scripts/crew-config.py validate crew.toml
```

Each problem prints as `file:key: reason`, where `key` is the dotted path
(`backends.change.name`, `engines.default.order[0]`); exit 1 on any problem,
0 otherwise. It fails on: invalid TOML, a missing required key, an unknown
key, concern, runtime, backend, engine or effort, a wrong type, a malformed
capability, a host inventory problem (`[hosts.<name>]` and `[placement]`
above), and a token-shaped value anywhere in the file.

## Layers and precedence

`scripts/crew-config.py resolve --project <crew.toml> [--org-profile <path>]`
builds the effective profile from four layers, lowest precedence first
([portable spec P5](specs/portable.md#2-requirements), #110 decision):

| Layer | Source | Present |
|---|---|---|
| `core` | Schema defaults in the script: `repo.default_branch`, `engines.coordinator`, each tier's `effort`, and the chosen runtime's integer options | always |
| `default` | `profiles/default.toml` in eng-crew (13.12, [#124](https://github.com/mw-ding/eng-crew/issues/124)) | skipped while absent |
| `org` | The org / environment pack profile, read only from the `--org-profile` path; eng-crew never holds or names one | only when given |
| `project` | The project's `crew.toml` (`--project`) | always |

Merge rule: tables merge by key; scalars and arrays replace the lower
layer's value whole. TOML has no null, so a layer drops keys only by
replacing a table with a non-table. Doing that to a key under `identities`
(I1, I4), `backends` (capability declarations, I1–I5) or `engines` (I2) is
an error.

The merged profile must then pass every `validate` check, plus these
cross-key checks:

- the [unsupported-invariant rule](interfaces.md#capability-declaration):
  an operation declared `unsupported` whose invariant no other operation
  keeps fails the profile. Before the check, `resolve` fills each backend's
  operations that no layer declares from its pack manifest
  (`packs/<name>/manifest.toml`, #124; [packs](packs.md#capability-declaration)),
  printed with the layer `pack:<name>`. An operation still undeclared counts
  as `unsupported`;
- [single identity](interfaces.md#single-identity-profile): if
  `identities.reviewer.gh_user` equals `identities.builder.gh_user`,
  `backends.review.capabilities.post-verdict` must be `emulated (<how>)`;
- integer options, such as `runtime.options.builders`, must be at least 1.

On success it prints one `key = value  # layer` line per leaf key, naming
the layer that set it, and exits 0. Each problem prints as
`file:key: reason`, where `file` is the layer file that set the key, or
`(resolved)` for a key no layer set; exit 1.

```text
$ python3 scripts/crew-config.py resolve --project crew.toml
repo.owner = "acme"  # project
repo.default_branch = "main"  # core
runtime.options.builders = 3  # project
runtime.options.reviewers = 2  # core
```
