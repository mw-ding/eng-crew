# Team files

Configuration module for team files, split out of the
[profile reference](../profile.md) under the M26 modular organization
principle ([#676](https://github.com/mw-ding/eng-crew/issues/676)). It holds
the whole of the profile's [Team files](../profile.md#team-files) section:
the file's location and name, the `[team]` tables and shorthands, the
per-repo allowlist and an example, then resolution, the shared team instance
and migration. The team-only tables keep their schema in the profile's
[Keys](../profile.md#keys) section. Resolution follows the profile's
[Layers and precedence](../profile.md#layers-and-precedence), and the merged
result still passes its [Validate](../profile.md#validate) checks.

## Schema and example

One owner often runs more than one crew, and each crew serves several repos
([#634](https://github.com/mw-ding/eng-crew/issues/634)). A team file holds
the whole crew once, with a small section per repo. Keep it at
`<config-home>/teams/<team>.toml`, outside any release bundle and any repo
clone, so upgrades never touch it. The team name (`[a-z0-9-]`, 1–63
characters) keys the team's state root and tmux session. Set it with
`[team] name = "<team>"`, so a conventional `config.toml`, a renamed file or
a symlink to the file all resolve the same team (#1348). Without
`team.name`, the file name is the team name, as before, so a nameless file
keeps its current identity. Changing the team name, or adding one that
differs from the file name, moves the state root and session: stop the crew
and move the state with [`mdstack migrate`](../runtimes/tmux.md#mdstack-migrate)
first.

- `[team]` holds the optional `name` and every team-only table, in the shape described above:
  `runtime`, `backends`, `identities`, `engines`, `paths`, `flavor`,
  `hosts`, `placement`, `tools`, `size_budget`, `builder`, `sensitive` and
  `spec`.
  Three shorthands fill those tables, and explicit keys win over them:
  `pack = "<backend>"` names the backend for every concern the team leaves
  unset; `personas = { <role> = "<Name>" }` sets `identities.<role>.name`;
  `accounts = { all = "<login>", <role> = "<login>" }` sets
  `identities.<role>.gh_user`, and a named role beats `all`.
- `[repos.<name>]` holds only what differs per repo. `repo = "<owner>/<name>"`
  is required. The allowlist is: `default_branch`, `precheck` (the
  [`[builder.precheck]`](../profile.md#builderprecheck) table), `sensitive` (a list that
  replaces `sensitive.paths`), `spec` (a list that replaces
  [`spec.paths`](../profile.md#spec)), and the landing overrides `merge_grant`,
  `merge_grant_scope`, `mirror_deferral`, `lone_pr_land`, `train_min`,
  `train_window` and `train_local_checks` (as `runtime.options.*`). Any other key fails as
  team-only, and a per-repo key in `[team]` fails too.

```text
[team]
name = "md"
pack = "github"
personas = { coordinator = "Ash", builder = "Ben", reviewer = "Vera", synthesizer = "Sam" }
accounts = { all = "<bot-login>", reviewer = "<reviewer-login>" }
runtime = { name = "tmux", options = { builders = 6, reviewers = 8 } }
identities = { owners = ["<user-login>"] }
paths = { state_dir = "<state-dir>", worktree_root = "<worktree-root>" }

[repos.mdstack]
repo = "<owner>/mdstack"
merge_grant = "roadmap PRs per the tracking issue"
train_window = 120

[repos.widgets]
repo = "<owner>/widgets"
checkout = "~/src/widgets"
default_branch = "trunk"
sensitive = ["billing/**"]
```

## Resolution and team instance

Resolution is the [layer pipeline](../profile.md#layers-and-precedence), with `team` and
`repo` in place of `project`: `core < default < org < team < repo`. Every
`validate` and cross-key check still applies to the merged result. A problem
in a repo section's value prints as `<file>[repos.<name>]:<key>: reason`.
Name a repo with a project reference `<file>#<name>`. Every `--project` flag
resolves one (`crew-config.py resolve`, `sensitive`, the `mdstack` commands), and
a team file with one repo needs no `#<name>`. Commands that also need the
repo's clone (`mdstack spawn`, `mdstack train`) find it at the repo section's
`checkout` key, which sets that repo's `paths.checkout`: absolute, or relative
to the team file's directory (to `paths.root` when set). Without it, the clone
is the team file's directory, so a team file outside every clone needs
`checkout` in each repo section (#1287). A single-repo `config.toml` is a
team file with one repo, and it resolves unchanged.

One team instance serves all of its repos. In a team file,
`paths.state_dir` resolves to `<state_dir>/<team>`, the state root. Each repo
gets its own subfolder, `<owner>__<repo>`, as before. The tmux session
defaults to `crew-team-<team>` (an explicit `runtime.options.session` wins).
`mdstack up --team <file>` validates every repo, then:

- renders each repo's briefs into its subfolder;
- writes a team coordinator brief, `<root>/coordinator.md`, listing each repo's
  reference, state directory and rendered brief;
- installs the Stop guard once per repo state;
- opens the one coordinator window, with `CREW_STATE` as the root,
  `CREW_TEAM` as the team file and `CREW_PROJECT` as the first repo.

It starts no pool leads yet, because lead windows have fixed indexes per
session. `mdstack down --project <file>#<name>` stops the whole shared session.

## Multi-project routing design

The [M51 team/project contract](../specs/team.md#9-team-and-project-separation-1318-design-only)
extends this schema with closed project context and rigor tightening. Its
proposed keys, shared admission and pool startup are design only; the
current resolution and startup above remain shipped behavior. The contract
uses a two-repo collision example and specifies per-repo land authority.
For #1318, 7.0+ is fresh and migration is not needed; the conversion below
remains operator guidance for existing team-file deployments.

## Migration: two `config.toml` files to one team file

1. Create `<config-home>/teams/<team>.toml`. Move every table that is the same
   in both files under `[team]` (`[runtime]` becomes `[team.runtime]`, and so
   on), and drop `[repo]`.
2. For each repo, add `[repos.<name>]` with `repo = "<owner>/<name>"`. Then
   move in the allowlisted keys that differ: `paths.checkout` as `checkout`
   (each repo's clone, needed once the team file sits outside it), `default_branch`,
   `builder.precheck` as `precheck`, `sensitive.paths` as `sensitive`,
   `spec.paths` as `spec`, and the landing options from `runtime.options`.
3. Any other key that differs between the two files is team-only. Pick one
   value, or keep that repo in its own team file.
4. Check each repo: run `crew-config.py resolve --project <file>#<name>` and
   compare the output with `resolve --project <old config.toml>`. Only
   provenance, `paths.state_dir` (now under `<team>/`),
   `runtime.options.session` and a `paths.checkout` you added should differ.
5. Stop both crews (`mdstack down --project <old config.toml>`), move each
   repo's state folder under `<state_dir>/<team>/`, and run
   `mdstack up --team <file>`.
