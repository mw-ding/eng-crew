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
[protocol](protocol.md) owns them. Layer merging (13.11,
[#123](https://github.com/mw-ding/eng-crew/issues/123)) and the default
profile (13.12, [#124](https://github.com/mw-ding/eng-crew/issues/124)) come
later; until then `validate` checks one complete file.

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

### `[runtime]`

| Key | Type | Default | Replaces |
|---|---|---|---|
| `name` | string: `grok-bot` or `tmux` ([runtimes](runtimes/README.md)) | *required* | none (was implicit: Grok Bot) |
| `options` | table, keys per runtime below | `{}` | none |

`grok-bot` takes no options. `tmux` ([binding](runtimes/tmux.md)):

| Option | Type | Default | Replaces |
|---|---|---|---|
| `session` | string | `crew-<owner>-<repo>` | the session name in [Layout and naming](runtimes/tmux.md#layout-and-naming) |
| `builders` | integer | `5` | builder band cap ([Q6](runtimes/tmux.md#q6-concurrency)) |
| `reviewers` | integer | `2` | reviewer pass cap ([Q6](runtimes/tmux.md#q6-concurrency)) |

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
| `markers` | `write`, `read` |
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

`gh_user` is the only mechanism today: a GitHub login whose token is derived
at use, `GH_TOKEN=$(gh auth token --user <login>)` (on tmux via
`CREW_IDENTITY`, [Q5](runtimes/tmux.md#q5-identities)). A reviewer equal to
the author is the single-identity profile; `validate` allows it.

### `[engines]`

| Key | Type | Default | Replaces |
|---|---|---|---|
| `coordinator` | string: `claude-code` or `codex` | `"claude-code"` | none ([tmux Q3](runtimes/tmux.md#q3-coordinator-engine)) |
| `trivial`, `default`, `deep` | table, *required* each | *required* | the [current routing](roles.md#current-routing) row of that tier |
| `<tier>.order` | list of `<engine>/<model>` strings, first choice first | *required* | `<engine>`, `<model>` |
| `<tier>.effort` | string: `low`, `medium` or `high` | `low` / `medium` / `high` by tier ([tiers](roles.md#tiers)) | `<effort>` |

`<engine>` is one of `claude-code`, `codex`, `muse`, `opencode`
([how to run each engine](roles.md#how-to-run-each-engine)); any other engine
fails. The [hard rules](roles.md#hard-rules) still apply to whatever the order
names.

### `[paths]`

| Key | Type | Default | Replaces |
|---|---|---|---|
| `state_dir` | string | *required* | `<state-dir>` |
| `worktree_root` | string | *required* | `<worktree-root>` |

## Validate

```sh
python3 scripts/crew-config.py validate crew.toml
```

Each problem prints as `file:key: reason`, where `key` is the dotted path
(`backends.change.name`, `engines.default.order[0]`); exit 1 on any problem,
0 otherwise. It fails on: invalid TOML, a missing required key, an unknown
key, concern, runtime, backend, engine or effort, a wrong type, a malformed
capability, and a token-shaped value anywhere in the file.
