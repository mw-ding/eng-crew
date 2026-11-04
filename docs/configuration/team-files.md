# Team files

Configuration module for the team file schema, split out of the
[profile reference](../profile.md) under the M26 modular organization
principle ([#676](https://github.com/mw-ding/eng-crew/issues/676)). It is the
opening of the profile's
[Team files](../profile.md#team-files) section: the file's location and name,
the `[team]` tables and shorthands, the per-repo allowlist and an example.
The team-only tables keep their schema in the profile's
[Keys](../profile.md#keys) section. Resolution, the shared team instance and
migration stay in the profile below the
[Team files](../profile.md#team-files) heading.

## Schema and example

One owner often runs more than one crew, and each crew serves several repos
([#634](https://github.com/mw-ding/eng-crew/issues/634)). A team file holds
the whole crew once, with a small section per repo. Keep it at
`<config-home>/teams/<team>.toml`, outside any release bundle and any repo
clone, so upgrades never touch it. The file name is the team name
(`[a-z0-9-]`, 1–63 characters).

- `[team]` holds every team-only table, in the shape described above:
  `runtime`, `backends`, `identities`, `engines`, `paths`, `flavor`,
  `hosts`, `placement`, `tools`, `size_budget`, `builder` and `sensitive`.
  Three shorthands fill those tables, and explicit keys win over them:
  `pack = "<backend>"` names the backend for every concern the team leaves
  unset; `personas = { <role> = "<Name>" }` sets `identities.<role>.name`;
  `accounts = { all = "<login>", <role> = "<login>" }` sets
  `identities.<role>.gh_user`, and a named role beats `all`.
- `[repos.<name>]` holds only what differs per repo. `repo = "<owner>/<name>"`
  is required. The allowlist is: `default_branch`, `precheck` (the
  [`[builder.precheck]`](../profile.md#builderprecheck) table), `sensitive` (a list that
  replaces `sensitive.paths`), and the landing overrides `merge_grant`,
  `mirror_deferral`, `lone_pr_land`, `train_min`, `train_window` and
  `train_local_checks` (as `runtime.options.*`). Any other key fails as
  team-only, and a per-repo key in `[team]` fails too.

```text
[team]
pack = "github"
personas = { coordinator = "Ash", builder = "Ben", reviewer = "Vera", synthesizer = "Sam" }
accounts = { all = "<bot-login>", reviewer = "<reviewer-login>" }
runtime = { name = "tmux", options = { builders = 6, reviewers = 8 } }
identities = { owners = ["<user-login>"] }
paths = { state_dir = "<state-dir>", worktree_root = "<worktree-root>" }

[repos.eng-crew]
repo = "<owner>/eng-crew"
merge_grant = "roadmap PRs per the tracking issue"
train_window = 120

[repos.widgets]
repo = "<owner>/widgets"
default_branch = "trunk"
sensitive = ["billing/**"]
```
