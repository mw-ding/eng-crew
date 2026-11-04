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
| `manifest.toml` | yes | `[pack]` (`name`, `commands`; `eng_crew_version` for a pack outside eng-crew; optional `version`, the [pack's own release](#pack-version)) and the [capability declaration](#capability-declaration) |
| `profile.toml` | no | Org-layer values for [`resolve`](profile.md#layers-and-precedence): any `crew.toml` key, usually `backends.<concern>.name` and overrides |
| `docs/` | yes | Binding docs: one command or API call per operation of [interfaces](interfaces.md), as [backends/github.md](backends/github.md#interface-mapping) does for GitHub; `commands` points at it |
| `render/` | no | Per-file [render overlay](#render-overlay): `backends/<name>.toml` and any template to change, laid out like `templates/` |

`crew-config.py validate <pack>/manifest.toml` checks a manifest
([Pack manifest](profile.md#pack-manifest)).

## Version pin

`pack.eng_crew_version` names the eng-crew version the pack was checked
against by its release id: a release tag once eng-crew tags releases, until
then the full 40-character commit SHA of eng-crew `main`. Where the
installed eng-crew is released with `release_id = "commit"`
([commit release id](release.md#commit-release-id)), the pin is the full
40-character hash of a landed cut commit recorded by
`release.record-release`; any other hash is not a release. Compatibility rule:

- A pack is supported only at its pinned version. Install the eng-crew
  checkout that matches the pin, by tag or by hash.
- To move the pin, run `validate` on the manifest and `resolve` with the
  pack's profile against the new checkout; both must pass. Then bump the
  pin in the pack's repo.
- An operation added to [interfaces](interfaces.md) after the pin is
  undeclared in an older manifest, so it counts as `unsupported`; if that
  leaves an invariant, `resolve` fails closed rather than weakening it.

### Pack version

`pack.version` is optional and names the pack's own release, for a pack
released on its own schedule. It is a SemVer string with the
[Versioning](deliverables.md#versioning) rules but no leading `v`
(`0.5.0`, `1.2.0-rc.1`). It differs from the pin: `eng_crew_version` names
the eng-crew release the pack was checked against; `version` names the
pack's release and gates nothing.

- `validate` refuses a malformed `version`; a manifest without one stays
  valid.
- `resolve` with an external pack prints it after the profile keys as
  `pack.version = "<version>"  # pack:<name>`. It is metadata only: the
  effective profile gets no `pack` table.
- Bootstrap and upgrade record `"pack": {"name", "version"}` in
  `install.json`, and `crew doctor` shows it as the `pack` row. Upgrade
  updates the record when only the pack version changed.
- Without `version`, none of these outputs or fields appear.

## Capability declaration

`[capabilities.<concern>]` lists every operation of that concern as
`supported`, `unsupported` or `emulated (<how>)`, the
[capability declaration](interfaces.md#capability-declaration) of
13.9. `resolve` folds the manifest of each chosen backend
(`packs/<name>/manifest.toml`, or the explicit external manifest) under every config layer: a profile's
`backends.<concern>.capabilities` value wins, and the output names the
manifest as `pack:<name>`. An operation neither declares counts as
`unsupported` in the unsupported-invariant rule.

## Wiring

A project picks backends by name in its `crew.toml`
(`backends.<concern>.name`) and points at an org pack when it resolves:

```sh
python3 scripts/crew-config.py resolve --project crew.toml \
  --org-profile <pack-path>/profile.toml \
  --pack-manifest <pack-path>/manifest.toml
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

The pack path stays with the install, never in eng-crew. `--pack-manifest`
loads and validates the external manifest, then admits its `pack.name` as
a backend alongside `github`. With an explicit or recorded org profile, its adjacent
`manifest.toml` is used when present, unless `--pack-manifest` overrides it;
a recorded pack directory without `profile.toml` still supplies its `manifest.toml`.
Names use lowercase letters and digits
separated by hyphens; new backends require `pack.eng_crew_version`.
`validate crew.toml --pack-manifest <pack-path>/manifest.toml` uses the same
declaration. Unknown names still fail. External capabilities fold below
profile overrides with provenance `external-pack`; other backends continue
to use their bundled manifests. Invalid or unreadable external manifests fail.

## Render overlay

The renderer searches a pack's `render/` directory per file before
`templates/` (or `--inputs`). The pack directory is the org profile's
directory, else `paths.pack`. A pack that only adds a backend holds
`render/backends/<name>.toml`; a pack that changes one brief adds that one
file, such as `render/runtimes/tmux/builder.md`. Every other file still comes
from upstream, so the output equals the upstream render except for the
overridden files and the pack's mapped commands. `crew-render.py`,
`crew bootstrap` (self-test and preview), `crew up`, `crew upgrade` and
`check-skill-drift.py --project` all apply it. Lookup order:
[scripts](../scripts/README.md#renderer).

Every backend command in the tmux briefs goes through an
`<op:<concern>.<operation>>` token, so a pack's backend map replaces all of
them. That includes the brief's CLI conventions (`change.cli-name`,
`change.cli-repo-flag`, `change.cli-unscoped`) and the state-tag and
gate-status edits ([interfaces](interfaces.md)). A pack declares a
capability for each one as usual. A map value is substituted as written, so
a multi-line value keeps the brief's line breaks.

### Placeholder declaration

Command values may use the renderer's run-time placeholders. A backend
whose identifiers differ declares its own in its backend map:

```toml
[placeholders]
kept = ["item-id", "version-id"]

[change]
list-open = "<cli> list --open --item <item-id>"
```

Declared names (`[a-z][a-z0-9-]*`, never an install-time placeholder such
as `<owner>`) render verbatim inside that map's commands. An undeclared
name still fails with `unknown placeholder <name>`.

### Render-time notes

`runtime.options.notes.render.<role>` lists files appended to that role's
rendered brief at render time. Any role in the registry and the `builder-lead`
and `reviewer-lead` briefs are accepted
([profile](profile.md#runtime)). Unlike launch-time notes, they
count toward `size_budget` and the drift check covers them.

## Denylist check

`check-repo.py --only denylist` reads the file named by `CREW_DENYLIST`
(one name per line, outside this repo) and fails on any whole-word,
case-insensitive match in a tracked file. Unset means skip. See
[scripts](../scripts/README.md#denylist).
