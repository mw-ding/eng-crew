# Migrating from the old layout and CLI name

For installs and packs set up before 6.0.0, before the CLI was named
`mdstack`, or before 7.0.0. Three changes need action: the modular layout
moved files out of `scripts/` in 6.0.0, the CLI `crew` became `mdstack` in
the release after 6.0.0, and the product names `eng-crew` became `mdstack`
in 7.0.0 ([product names](#product-names-700)). The first two keep
compatibility shims for a limited time; the 7.0.0 rename has none, so a 6.x
install is reinstalled from scratch. This guide is
navigation only: the [CHANGELOG](../../CHANGELOG.md) entries for 6.0.0
(issue #1226) and for the rename (#1233) are the record, and
[release.md](../release.md#update-path) owns upgrades.

## What to do, in order

1. **Upgrade** to the release that ships `cli/mdstack`
   ([update path](../release.md#update-path)):
   `mdstack upgrade --project <home>/crew.toml --version vX.Y.Z --dry-run`,
   then `--yes`. On an install that has no `cli/mdstack` yet, run the same
   command as `<mdstack>/scripts/crew upgrade ...`.
2. **Re-point the CLI** everywhere you call it: shell aliases, wrappers,
   cron jobs and `CREW_BIN` should name `<mdstack>/cli/mdstack`
   ([CLI name](#cli-name)). Rerun `mdstack layout --project <home>/crew.toml
   --write` to rewrite the start wrappers.
3. **Re-point old paths** in your profile, hooks, remote forced commands and
   scripts ([old paths](#old-paths-to-modules)).
4. **Restart:** `mdstack up --project <home>/crew.toml`. It re-points a
   turn-end guard hook that still names the old `crew` path.
5. **Update your pack**, if you have one ([packs](#packs)).
6. Check with `mdstack doctor --project <home>/crew.toml`.

Optional, at any time: move to the
[home-level layout](../runtimes/tmux.md#home-level-layout-1178) with
`mdstack migrate --to`
([relocation](../bootstrap.md#home-level-layout-and-relocation-1178)), or
rename the repo with the [repo rename runbook](../runbooks/repo-rename.md).

## CLI name

`cli/mdstack` is the entry point. `cli/crew` is a shim kept for one release:
it prints `crew: deprecated, use mdstack` on stderr and then runs `mdstack`
unchanged, so scripts keep working while you move them. It is removed in the
release after the one that introduced `mdstack`; see that release's notes for
the version. `scripts/crew` still runs the CLI through the path shims below.

These keep their names: the `CREW_*` environment variables, `crew.toml`, the
`crew.d/` module directory, state paths, and the `crew:` labels and markers.
Only the command changes: `crew up` is now `mdstack up`, and so on for every
subcommand. Anchors to the [tmux binding](../runtimes/tmux.md)'s command
sections are now `#mdstack-<command>`.

## Product names (7.0.0)

7.0.0 renames the product from `eng-crew` to `mdstack` (#1312), after the
repo moved to `github.com/mw-ding/mdstack`:

| 6.x name | 7.0.0 name |
|---|---|
| Release bundle `eng-crew-<version>.tar.gz`, top directory `eng-crew-<version>/` | `mdstack-<version>.tar.gz`, `mdstack-<version>/` |
| Host toolkit `toolkit/eng-crew-<version>/` | `toolkit/mdstack-<version>/` |
| Install link `<state>/eng-crew` | `<state>/mdstack` |
| Profile key `paths.eng_crew` | `paths.mdstack` |
| Pack key `pack.eng_crew_version` | `pack.mdstack_version` |

The old names are not accepted: no alias, compatibility link or migration
step. Reinstall from scratch with a 7.0.0 bundle ([README: Install](../../README.md#install)):
download and extract `mdstack-<version>.tar.gz`, set `paths.mdstack` to
`<state-dir>/<owner>__<repo>/mdstack` in your profile, run
`mdstack bootstrap`, and remove the old `<state>/eng-crew` link and
`eng-crew-<version>/` bundle by hand. A pack renames `eng_crew_version` to
`mdstack_version` in its manifest.

`crew:` labels, markers and `CREW_*` variables keep their names.

## Old paths to modules

6.0.0 moved each file to its module
([module layout](../specs/team.md#4-target-module-layout)):

| Old path | New path |
|---|---|
| `scripts/crew` | `cli/crew`, now a shim for `cli/mdstack` |
| `scripts/crew-config.py`, `crew-render.py`, `crew-roles.py` | `core/` |
| `scripts/crew.d/*` | `environments/terminal/crew.d/*` |
| `scripts/crew-session.py`, `crew-proc.py` | `environments/terminal/` |
| `scripts/crew-remote.py` | `environments/terminal/remote/crew-remote.py` |
| `scripts/session.d/<backend>.py` | `environments/terminal/sessions/<backend>/adapter.py` |
| `scripts/crew-harness.py` | `harnesses/crew-harness.py` |
| `scripts/harness.d/<engine>.py` | `harnesses/<engine>/adapter.py` |
| `scripts/crew-repo.py` | `connectors/github/crew-repo.py` |
| `packs/github/manifest.toml` | `connectors/github/manifest.toml` |
| `scripts/test-*.py` | `dev/tests/<module>/test-*.py` |

Through every 6.x release each moved script path stays a shim that runs the
moved file, an adapter left in `scripts/harness.d/` or `scripts/session.d/`
is still discovered, and `packs/github/manifest.toml` stays a copy. Tests
have no shim. **All of these are removed in 7.0.0**, so point everything at
the new paths before you upgrade to it. The full inventory, with each shim,
is in [deliverables](../deliverables.md).

## Packs

- A pack that brings code needs a `pack.toml` whose `framework` range
  includes the installed release, such as `">=6.0.0, <7.0.0"`; bootstrap and
  upgrade refuse a pack outside its range
  ([install pin and upgrade](../packs.md#install-pin-and-upgrade)).
- Move a harness adapter kept in `scripts/harness.d/` into the pack as
  `harnesses/<name>/adapter.py` and list it under `[provides]`.
- Read the GitHub manifest from `connectors/github/`.
- Replace `crew` with `mdstack` in the pack's docs and CI, and run
  `mdstack pack test <dir>` there ([pack author guide](pack-authoring.md)).
