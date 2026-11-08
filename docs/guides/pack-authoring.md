# Writing a pack

A pack carries what eng-crew must not: an organization's own connectors,
harness adapters, environment defaults, skills and profile values. It lives
in its own repo and references eng-crew, never the other way round
([direction rule](../packs.md#direction-rule)). This guide walks through
building one. It is navigation only: [packs.md](../packs.md) owns the
format, discovery, floors and the conformance kit.

## Pack format

A pack is a directory, usually a git repo of its own:

```text
my-pack/
  pack.toml                          # name, framework range, what it provides
  profile.toml                       # optional org layer: any crew.toml key
  connectors/<name>/manifest.toml    # a connector's capability declaration
  connectors/<name>/action.py        # optional actions binding it names
  harnesses/<name>/adapter.py        # a harness adapter
  environments/<runtime>/defaults.toml
  skills/<name>/SKILL.md
  docs/                              # binding docs: one command per operation
  render/                            # optional per-file brief overrides
```

`pack.toml` declares the eng-crew releases the pack supports and what it
provides ([pack plug-ins](../packs.md#pack-plug-ins)):

```toml
[pack]
name = "example"
version = "0.1.0"                 # optional, the pack's own SemVer
framework = ">=6.0.0, <7.0.0"     # eng-crew releases the pack supports

[provides]
connectors = ["example-tracker"]
harnesses = ["example-agent"]
environments = ["tmux"]
skills = ["example-review"]
```

A pack without `pack.toml` is config-only: a root `manifest.toml` pinned by
`eng_crew_version`, an optional `profile.toml` and its docs, as in the
[layout](../packs.md#layout) and [version pin](../packs.md#version-pin).
Keep organization names out of eng-crew itself: its
[denylist check](../packs.md#denylist-check) fails on them.

## Plug-in points

| Point | Pack path | How the install uses it |
|---|---|---|
| Connector | `connectors/<name>/manifest.toml` | Picked by `backends.<concern>.name`; its capabilities fold in as `pack:<name>` ([capability declaration](../packs.md#capability-declaration)) |
| Harness | `harnesses/<name>/adapter.py` | An engine name in `[engines]`; `mdstack spawn` launches it ([harness adapters](../runtimes/harness-adapters.md)) |
| Environment defaults | `environments/<runtime>/defaults.toml` | The pack layer when `runtime.name` matches |
| Skill | `skills/<name>/SKILL.md` | Listed beside the built-in role skills |
| Org profile | `profile.toml` | The pack layer of [resolve](../profile.md#layers-and-precedence): core, default profile, pack, project |
| Brief overrides | `render/<path>` | Searched before `templates/`, one file at a time ([render overlay](../packs.md#render-overlay)) |
| Harness pointers | the file `pack.harness` names | Installed by `mdstack bootstrap --harness` ([harness pointers](../packs.md#harness-pointers)) |

A pack adds names and never replaces a built-in one. It may tighten rules,
such as a stricter flavor, extra sensitive paths or extra skills, but the
loader refuses one that loosens a core floor
([floors](../packs.md#floors)).

## Wire it into an install

Record the pack directory in the project's `crew.toml`, then check what it
contributes:

```toml
[paths]
pack = "/path/to/my-pack"
```

```sh
mdstack pack list --project ~/crew-home/crew.toml
```

Each line names an item's kind, name, source (`core`, `pack:<name>` or
`core+pack:<name>`) and path ([discovery](../packs.md#discovery)). Bootstrap
and upgrade refuse a pack whose `framework` range excludes the installed
release, or whose checkout is not clean, and record its commit in
`install.json` ([install pin and upgrade](../packs.md#install-pin-and-upgrade)).
[Wiring](../packs.md#wiring) covers `--org-profile` and `--pack-manifest`.

## Run the conformance kit

The conformance kit runs the public [actions](../../actions/README.md)
contract tests against the pack's adapters with fakes. Run it in the pack's
own CI against the eng-crew release the pack supports:

```sh
<eng-crew>/cli/mdstack pack test /path/to/my-pack
```

Exit 0 means every check passed. It checks that each connector manifest
validates and its actions binding keeps the [CLI contract](../../actions/cli.md),
and that each harness adapter has the module interface the built-ins have
and launches a fake executable ([conformance kit](../packs.md#conformance-kit)).
The fixture pack `dev/tests/core/fixtures/packs/example` is a working
example of every plug-in point.

## Keep up with releases

- Widen `framework` only after `mdstack pack test` and `resolve` pass
  against the new release.
- A new interface operation is `unsupported` in an older manifest until
  you declare it; `resolve` fails closed when that leaves an invariant.
- Moving from the old layout or CLI name: [migration](migration.md#packs).
