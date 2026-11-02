# Packs

A pack is a backend's adapter: its capability declaration, its command
mapping and, for an organization, the profile values that pick it. The
GitHub pack ships here ([packs/github/](../packs/github/manifest.toml));
an organization's own pack lives in its own repo, outside eng-crew, pinned
to an eng-crew version (portable eng-crew, roadmap 13.15,
[#127](https://github.com/mw-ding/eng-crew/issues/127);
[portable spec P5, P6](specs/portable.md#2-requirements)).

This page adds no rule, gate, cap, marker field or label; the
[protocol](protocol.md) owns them. Writing, hosting or fetching an org pack
is out of scope.

## Direction rule

Packs reference eng-crew; eng-crew never references a pack outside this
repo. No file here names an organization's internal tools, commands, URLs
or specs (spec P6). The [denylist check](#denylist-check) guards it.

## Layout

| Path in the pack | Required | Contents |
|---|---|---|
| `manifest.toml` | yes | `[pack]` (`name`, `commands`; `eng_crew_version` for a pack outside eng-crew) and the [capability declaration](#capability-declaration) |
| `profile.toml` | no | Org-layer values for [`resolve`](profile.md#layers-and-precedence): any `crew.toml` key, usually `backends.<concern>.name` and overrides |
| `docs/` | yes | Binding docs: one command or API call per operation of [interfaces](interfaces.md), as [backends/github.md](backends/github.md#interface-mapping) does for GitHub; `commands` points at it |
| `render/` | no | Render overrides for the renderer (13.13, [#125](https://github.com/mw-ding/eng-crew/issues/125)), in the shape that renderer defines |

`crew-config.py validate <pack>/manifest.toml` checks a manifest
([Pack manifest](profile.md#pack-manifest)).

## Version pin

`pack.eng_crew_version` names the eng-crew version the pack was checked
against: a release tag once eng-crew tags releases, until then the full
40-character commit SHA of eng-crew `main`. Compatibility rule:

- A pack is supported only at its pinned version. Install the eng-crew
  checkout that matches the pin.
- To move the pin, run `validate` on the manifest and `resolve` with the
  pack's profile against the new checkout; both must pass. Then bump the
  pin in the pack's repo.
- An operation added to [interfaces](interfaces.md) after the pin is
  undeclared in an older manifest, so it counts as `unsupported`; if that
  leaves an invariant, `resolve` fails closed rather than weakening it.

## Capability declaration

`[capabilities.<concern>]` lists every operation of that concern as
`supported`, `unsupported` or `emulated (<how>)`, the
[capability declaration](interfaces.md#capability-declaration) of
13.9. `resolve` folds the manifest of each chosen backend
(`packs/<name>/manifest.toml`) under every config layer: a profile's
`backends.<concern>.capabilities` value wins, and the output names the
manifest as `pack:<name>`. An operation neither declares counts as
`unsupported` in the unsupported-invariant rule.

## Wiring

A project picks backends by name in its `crew.toml`
(`backends.<concern>.name`) and points at an org pack when it resolves:

```sh
python3 scripts/crew-config.py resolve --project crew.toml \
  --org-profile <pack-path>/profile.toml
```

The project can instead record the pack directory in its own `crew.toml`:

```toml
[paths]
pack = "<pack-path>"
```

`resolve` reads that directory's optional `profile.toml` as the org layer.
Relative directories resolve from the project file, independent of the
current directory. An explicit `--org-profile` overrides this selection.
Missing directories and malformed profiles fail; a pack without a profile
adds no org layer. Core/default/org/project precedence is unchanged.
Bootstrap checks the recorded pack's version pin just as it does for an
explicit `--org-profile`.

The pack path stays with the install, never in eng-crew. Today `validate`
accepts only the `github` backend, so an org pack can set and override
values through its `profile.toml` but cannot add a backend; `resolve` reads
manifests only from this repo's `packs/`.

## Denylist check

`check-repo.py --only denylist` reads the file named by `CREW_DENYLIST`
(one name per line, outside this repo) and fails on any whole-word,
case-insensitive match in a tracked file. Unset means skip. See
[scripts](../scripts/README.md#denylist).
