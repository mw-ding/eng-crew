# Moving to 7.0.0: reinstall from scratch

7.0.0 is a fresh install. It carries no 6.x or older install forward: no
compatibility shims, aliases, links or migration steps (#1312). The
[CHANGELOG](../../CHANGELOG.md) 7.0.0 entries are the record, and
[release.md](../release.md#update-path) owns upgrades between 7.x releases.

## What to do, in order

1. **Stop the old crew:** `down --preserve` with the old install's CLI, and
   land or park any open work.
2. **Install 7.0.0** from the release bundle
   ([README: Install](../../README.md#install)): download and check
   `mdstack-<version>.tar.gz`, extract it, and run
   `<mdstack>/cli/mdstack bootstrap --project ~/.mdstack/config.toml --dry-run`,
   then `--yes`.
3. **Update your profile and scripts** to the 7.0.0 names below: shell
   aliases, wrappers, cron jobs, hooks, remote forced commands and
   `CREW_BIN` name `<mdstack>/cli/mdstack` and the module paths. Rerun
   `mdstack layout --project ~/.mdstack/config.toml --write` for the start
   wrappers.
4. **Update your pack**, if you have one ([packs](#packs)).
5. **Start:** `mdstack up --project ~/.mdstack/config.toml`, then check with
   `mdstack doctor --project ~/.mdstack/config.toml`.
6. Remove the old install by hand: the `<state>/eng-crew` link and the
   `eng-crew-<version>/` bundle.

## Product names (7.0.0)

7.0.0 renames the product from `eng-crew` to `mdstack`, after the repo moved
to `github.com/mw-ding/mdstack`. The old names are not accepted:

| Old name | 7.0.0 name |
|---|---|
| Release bundle `eng-crew-<version>.tar.gz`, top directory `eng-crew-<version>/` | `mdstack-<version>.tar.gz`, `mdstack-<version>/` |
| Host toolkit `toolkit/eng-crew-<version>/` | `toolkit/mdstack-<version>/` |
| Install link `<state>/eng-crew` | `<state>/mdstack` |
| Profile key `paths.eng_crew` | `paths.mdstack` |
| Pack key `pack.eng_crew_version` | `pack.mdstack_version` |
| CLI `crew` (`cli/crew`, `scripts/crew`) | `mdstack` (`cli/mdstack`) |

`crew:` labels, markers, the `crew.d/` module directory and the `CREW_*`
variables keep their names. 7.1 renames the profile to `config.toml` and
moves the default layout under `~/.mdstack/` (#1316), with no fallback to
`crew.toml` or the old `~/crew-home/` and `~/.crew/` defaults.

## Old paths to modules

6.0.0 moved each file to its module
([module layout](../specs/team.md#4-target-module-layout)); 7.0.0 removed
the old paths:

| Old path | Path |
|---|---|
| `scripts/crew` | `cli/mdstack` |
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

An adapter left in `scripts/harness.d/` or `scripts/session.d/` is no longer
discovered.

## Packs

- Rename `eng_crew_version` to `mdstack_version` in the pack manifest, or
  give a `pack.toml` `framework` range that includes 7.0.0, such as
  `">=7.0.0, <8.0.0"`; bootstrap refuses a pack outside its range
  ([install pin and upgrade](../packs.md#install-pin-and-upgrade)).
- Move a harness adapter kept in `scripts/harness.d/` into the pack as
  `harnesses/<name>/adapter.py` and list it under `[provides]`.
- Read the GitHub manifest from `connectors/github/`.
- Replace `crew` with `mdstack` in the pack's docs and CI, and run
  `mdstack pack test <dir>` there ([pack author guide](pack-authoring.md)).
