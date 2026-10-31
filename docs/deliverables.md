# Deliverables and versioning (design)

What eng-crew ships, how it is packaged, how it is versioned and what each
version promises (roadmap R1.1,
[#145](https://github.com/mw-ding/eng-crew/issues/145); umbrella
[#110](https://github.com/mw-ding/eng-crew/issues/110);
[portable spec P9](specs/portable.md#2-requirements)). How a version is cut
and taken is in [release.md](release.md).

This page adds no rule, gate, cap, marker field or label; the
[protocol](protocol.md) owns them. The bundle build
([#236](https://github.com/mw-ding/eng-crew/issues/236)) and the release
workflow with the bundle attach
([#218](https://github.com/mw-ding/eng-crew/issues/218),
[#246](https://github.com/mw-ding/eng-crew/issues/246)) are implemented
([release.md](release.md)).

## Terms

- **Deliverable:** a path an environment installs or loads at run time (a
  role reads it, a script runs, the renderer consumes it). Deliverables are
  the public surface that [versioning](#versioning) covers.
- **Internal:** a path only maintainers of this repo use. Changing it never
  changes the version number.
- **Source / generated:** this repo holds only source. Rendered briefs and
  routines, and the release bundle, are generated and never committed
  (golden test fixtures excepted).

## Inventory

Every tracked path falls in exactly one row. Runtime `all` means every
runtime; `grok-bot` and `tmux` are the
[runtime bindings](runtimes/README.md).

| Path | Class | Runtime(s) | Source / generated | Why |
|---|---|---|---|---|
| `docs/protocol.md`, `docs/concepts.md`, `docs/roles.md`, `docs/architecture.md`, `docs/interfaces.md`, `docs/verification.md`, `docs/observe.md`, `docs/self-improve.md`, `docs/merge-enforcement.md` | Deliverable: protocol bundle (core) | all | source | The text roles load and cite |
| `docs/runtimes/README.md` | Deliverable: protocol bundle (runtime contract) | all | source | Contract every binding answers |
| `docs/runtimes/grok-bot.md` | Deliverable: protocol bundle (runtime binding) | grok-bot | source | Runtime gates, watches, routines |
| `docs/runtimes/tmux.md` | Deliverable: protocol bundle (runtime binding) | tmux | source | tmux binding and `crew` usage |
| `docs/backends/github.md` | Deliverable: protocol bundle (backend binding) | all | source | GitHub backend binding |
| `docs/profile.md`, `docs/packs.md` | Deliverable: profile and pack contract | all | source | Schema packs and installs validate against |
| `docs/metrics/decisions.md` | Deliverable: coordinator procedure | all | source | Metrics gate the coordinator runs |
| `docs/runbook-new-repo.md`, `docs/deliverables.md`, `docs/release.md` | Deliverable: install and upgrade docs | all | source | How to install, pin and upgrade |
| `templates/runtimes/grok-bot/**` | Deliverable: render input | grok-bot | source; rendered at install | Routines and trigger JSON |
| `templates/runtimes/tmux/**` | Deliverable: render input | tmux | source; rendered at install | Coordinator and role briefs |
| `templates/backends/github.toml` | Deliverable: render input | all | source | `<op:...>` command mapping |
| `templates/evidence/**`, `templates/product-readme.md`, `templates/intake-candidate.md`, `templates/metrics-regression-issue.md`, `templates/step-summary.md`, `templates/README.md` | Deliverable: templates | all | source | Evidence adapters, product README seed, cards and step lines |
| `profiles/default.toml` | Deliverable: profile | grok-bot | source | Default profile (spec P7) |
| `profiles/tmux.toml` | Deliverable: example profile | tmux | source | tmux example profile |
| `packs/github/**` | Deliverable: pack | all | source | GitHub capability declaration |
| `scripts/crew-config.py`, `scripts/crew-render.py` | Deliverable: install CLI | all | source | Validate, resolve, render |
| `scripts/crew`, `scripts/crew.d/**`, `scripts/crew-tmux.py` | Deliverable: runtime CLI | tmux | source | tmux crew CLI: entry point, per-command modules ([#224](https://github.com/mw-ding/eng-crew/issues/224)) and the tmux adapter |
| `scripts/check-skill-drift.py` | Deliverable: drift check | all | source | Render-vs-live check ([#128](https://github.com/mw-ding/eng-crew/issues/128)) |
| `scripts/step-summary.py`, `scripts/intake-sweep.py`, `scripts/metrics-refresh.py`, `scripts/metrics-decide.py` | Deliverable: role helpers | all | source | Builder and coordinator helpers |
| `scripts/README.md` | Deliverable: script usage | all | source | Usage of every shipped script |
| Coordinator session helpers (not in the repo yet) | Deliverable once upstreamed | all | source | [release.md](release.md#upstreaming-the-session-tooling) |
| `README.md`, `CHANGELOG.md` | Deliverable: bundle front page and release notes | all | source | Shipped as is |
| `scripts/check-repo.py`, `scripts/required-docs.txt`, `scripts/test-*.py`, `scripts/crew_testlib.py`, `scripts/fixtures/**` | Internal: guards and tests | n/a | source | Run by CI and release validation, not installed |
| `docs/specs/**`, `docs/lessons/**`, `docs/findings/**`, `docs/metrics/` (all but `decisions.md`), `docs/diagrams/**`, `docs/README.md` | Internal: maintainer docs, lessons, metrics, drills, diagrams | n/a | source | History and planning, not loaded by roles |
| `evidence/**`, `examples/**` | Internal: audit trail and worked example | n/a | source | Referenced, not installed |
| `changes/**` | Internal: unreleased CHANGELOG fragments | n/a | source | Assembled into `CHANGELOG.md` at the cut, then deleted ([CONTRIBUTING](../CONTRIBUTING.md#changelog)) |
| `AGENTS.md`, `CONTRIBUTING.md`, `.github/**`, `.markdownlint-cli2.yaml`, `.gitignore` | Internal: repo process and CI | n/a | source | Rules for building eng-crew itself |

Issue templates: none exist yet (no `.github/ISSUE_TEMPLATE/`). Product-repo
issue templates would be deliverables under `templates/`; this repo's own
stay internal with `.github/**`.

A new tracked path must be classified when it lands: the bundle build keeps
a machine-readable copy of this table and fails on an unclassified path
([release.md](release.md#follow-up-issues)).

## Packaging

| Decision | Choice | Alternatives considered |
|---|---|---|
| Unit | One bundle per release, `eng-crew-<version>.tar.gz`, holding every deliverable at its repo path, plus `VERSION` and `SHA256SUMS` | One tarball per runtime: more build and install paths for a few small files; revisit when a runtime's files outgrow this. A committed `dist/<runtime>/` tree: generated files in git drift, the same problem as hand mirroring |
| Per-runtime selection | At install: the renderer reads only the profile's `runtime.name` inputs, so one bundle serves every runtime | Rendering per runtime at release time: the render needs project values (`repo.owner`, identities, paths), which only the install has |
| Rendered output | Generated at install by `crew-render.py` from the bundle and the resolved profile, then deployed and drift-checked ([#128](https://github.com/mw-ding/eng-crew/issues/128)) | Shipping a reference render of `profiles/default.toml`: its values are placeholders, so it adds nothing over the templates |
| Harness layouts (Claude Code subagents and skills, Codex prompts, Grok Bot box skills) | Future render targets of the same bundle, decided by bootstrap ([#144](https://github.com/mw-ding/eng-crew/issues/144) install targets) | A Claude Code plugin as the release unit: one harness only |
| Links | A relative link from a deliverable to an internal path is rewritten to the file at the release tag on GitHub, so the bundle has no broken link and stays small | Shipping lessons and specs: they are history, not rules |
| Source archive | GitHub's automatic source archive of the tag stays available for a full checkout | none |

`scripts/crew` is an entry point plus per-command modules in `scripts/crew.d/`
([#224](https://github.com/mw-ding/eng-crew/issues/224)); the bundle ships the
whole module directory, so the split changes no packaging rule.

## Versioning

SemVer, tagged `vMAJOR.MINOR.PATCH` (owner decision, R1 milestone). The
public surface is the deliverables above. A change is breaking when an
environment installed at the previous version, or a pack pinned to it, would
stop working or stop complying without edits.

| Bump | Change to a deliverable |
|---|---|
| Major | A [§7](protocol.md#7-merge-gate-synthesizer) merge gate or the release gate added, removed, or satisfied differently; a `crew:v1` marker field removed, renamed, newly required or changed in meaning; a `crew:*` state tag removed, renamed or changed in meaning; a profile key removed, renamed, newly required or retyped; a pack manifest field or [interface](interfaces.md) operation removed or newly required; a runtime contract capability newly required; a `crew` command or flag removed, or a changed exit code or parsed output; a render placeholder removed or renamed |
| Minor | An optional profile key with a default; a new optional marker field old readers ignore; a new command, flag, template, script, runtime or backend binding; a new role duty that adds no gate |
| Patch | A fix that restores documented behaviour; wording that changes no rule; docs and test-only changes to deliverables |
| None | Any change to internal paths only |

Rules:

- A breaking CHANGELOG entry starts with `**Breaking:**` and carries a
  one-line migration step. The entries since the last tag decide the
  smallest allowed bump; the release approver checks the dispatched version
  against them ([release.md](release.md#steps)).
- Pre-release tags (`vX.Y.Z-rc.N`) are allowed for a smoke run and never
  satisfy a pin.
- Only the latest release is supported. Fixes go forward as a new release;
  there are no backport branches unless the owner asks for one.

## Compatibility promise

| To | Promise |
|---|---|
| Packs ([#127](https://github.com/mw-ding/eng-crew/issues/127)) | The [version pin](packs.md#version-pin) rule is unchanged: a pack is supported at its pinned version. Once tags exist the pin is a tag, not a SHA. Within one major, a manifest and pack profile that pass `validate` and `resolve` at the pin also pass at any later minor or patch, so moving the pin inside a major needs no pack edit |
| Installed environments ([#144](https://github.com/mw-ding/eng-crew/issues/144)) | Within one major, upgrading is re-render, drift check, deploy, with no profile edit. Across a major, the `**Breaking:**` entries list every edit the profile, pack or live copy needs |
| Live roles | A role's behaviour changes only when its environment takes a new version; nothing auto-updates ([release.md](release.md#update-path)) |

## First versions

Owner decisions (R1 milestone, [#219](https://github.com/mw-ding/eng-crew/issues/219)),
reflected here, not re-decided:

| Tag | Commit | Why |
|---|---|---|
| `v1.0.0` | The M12 cut: the commit that locked the README "v1 cut" (candidate `b2144a28198f26f6dc6cc0a8b2135a1e38d852ba`, PR #95; [#219](https://github.com/mw-ding/eng-crew/issues/219) confirms it) | Retro-tag of M1–M12 |
| `v2.0.0` | The M14 cut, after the [#139](https://github.com/mw-ding/eng-crew/issues/139) smoke | Major: M13/M14 change the profile layout, the runtime and the gates (the mirror gate is now a drift check), all breaking under the table above |

No `v1.x` release is cut between them. `v1.0.0` has no bundle (the bundle
build lands later); its source archive is the artifact.
