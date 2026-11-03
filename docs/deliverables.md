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
[runtime bindings](runtimes/README.md). The table is generated from
[`scripts/deliverables.txt`](../scripts/deliverables.txt), one row per manifest
row (a row may be a glob), so the manifest is the source and no PR edits the
table by hand: add or change a manifest row at its sorted place, then run
`python3 scripts/check-repo.py --fix`. `check-repo.py` fails on a stale table
and on an unsorted manifest, which would bring back the append point every PR
conflicts on ([#325](https://github.com/mw-ding/eng-crew/issues/325)).

<!-- inventory:begin generated from scripts/deliverables.txt by `python3 scripts/check-repo.py --fix`; do not edit -->

| Path | Class | Runtime(s) | Why |
|---|---|---|---|
| `.github/**` | Internal | n/a | Repo process and CI: rules for building eng-crew itself |
| `.gitignore` | Internal | n/a | Repo process and CI: rules for building eng-crew itself |
| `.markdownlint-cli2.yaml` | Internal | n/a | Repo process and CI: rules for building eng-crew itself |
| `AGENTS.md` | Internal | n/a | Repo process and CI: rules for building eng-crew itself |
| `CHANGELOG.md` | Deliverable | all | Bundle front page and release notes: shipped as is |
| `CONTRIBUTING.md` | Internal | n/a | Repo process and CI: rules for building eng-crew itself |
| `README.md` | Deliverable | all | Bundle front page and release notes: shipped as is |
| `changes/**` | Internal | n/a | Unreleased CHANGELOG fragments: assembled into `CHANGELOG.md` at the cut, then deleted ([CONTRIBUTING](../CONTRIBUTING.md#changelog)) |
| `docs/README.md` | Internal | n/a | Maintainer docs: the docs index, not loaded by roles |
| `docs/architecture.md` | Deliverable | all | Protocol bundle (core): the text roles load and cite |
| `docs/backends/github.md` | Deliverable | all | Protocol bundle (backend binding): GitHub backend binding |
| `docs/bootstrap.md` | Deliverable | all | Install and upgrade docs: how to install, pin and upgrade |
| `docs/concepts.md` | Deliverable | all | Protocol bundle (core): the text roles load and cite |
| `docs/deliverables.md` | Deliverable | all | Install and upgrade docs: how to install, pin and upgrade |
| `docs/diagrams/**` | Internal | n/a | Maintainer docs: diagrams, not loaded by roles |
| `docs/express-lane.md` | Deliverable | tmux | Profile and pack contract: express flavor design for the tmux binding ([#636](https://github.com/mw-ding/eng-crew/issues/636)) |
| `docs/findings/**` | Internal | n/a | Maintainer docs: findings buffer, not loaded by roles |
| `docs/flavors.md` | Deliverable | all | Profile and pack contract: flavor keys and the floor ([#156](https://github.com/mw-ding/eng-crew/issues/156)) |
| `docs/handoff.md` | Deliverable | all | Coordinator procedure: runtime handoff the coordinator runs (#157) |
| `docs/interfaces.md` | Deliverable | all | Protocol bundle (core): the text roles load and cite |
| `docs/lessons/**` | Internal | n/a | Maintainer docs: lessons log, history not loaded by roles |
| `docs/merge-enforcement.md` | Deliverable | all | Protocol bundle (core): the text roles load and cite |
| `docs/metrics/README.md` | Internal | n/a | Maintainer docs: metrics and drills, not loaded by roles |
| `docs/metrics/decisions.md` | Deliverable | all | Coordinator procedure: metrics gates the coordinator runs |
| `docs/metrics/owner-sla-drill.md` | Internal | n/a | Maintainer docs: metrics and drills, not loaded by roles |
| `docs/metrics/prs.csv` | Internal | n/a | Maintainer docs: metrics and drills, not loaded by roles |
| `docs/metrics/prs.md` | Internal | n/a | Maintainer docs: metrics and drills, not loaded by roles |
| `docs/metrics/regression-drills.md` | Internal | n/a | Maintainer docs: metrics and drills, not loaded by roles |
| `docs/observe.md` | Deliverable | all | Protocol bundle (core): the text roles load and cite |
| `docs/packs.md` | Deliverable | all | Profile and pack contract: schema packs and installs validate against |
| `docs/permit.md` | Deliverable | all | Protocol bundle (core): away permission auto-approve the owner installs ([#646](https://github.com/mw-ding/eng-crew/issues/646)) |
| `docs/profile.md` | Deliverable | all | Profile and pack contract: schema packs and installs validate against |
| `docs/protocol.md` | Deliverable | all | Protocol bundle (core): the text roles load and cite |
| `docs/release.md` | Deliverable | all | Install and upgrade docs: how to install, pin and upgrade |
| `docs/roles-registry.md` | Deliverable | all | Role registry contract: schema for domain roles (15.7, #317) |
| `docs/roles.md` | Deliverable | all | Protocol bundle (core): the text roles load and cite |
| `docs/runbook-new-repo.md` | Deliverable | all | Install and upgrade docs: how to install, pin and upgrade |
| `docs/runtimes/README.md` | Deliverable | all | Protocol bundle (runtime contract): contract every binding answers |
| `docs/runtimes/grok-bot.md` | Deliverable | grok-bot | Protocol bundle (runtime binding): runtime gates, watches, routines |
| `docs/runtimes/harness-adapters.md` | Deliverable | all | Protocol bundle (harness adapter interface): how a runtime launches, wakes and probes each agent CLI |
| `docs/runtimes/multi-device.md` | Deliverable | tmux | Protocol bundle (runtime binding): multi-device design for the tmux binding ([#158](https://github.com/mw-ding/eng-crew/issues/158)) |
| `docs/runtimes/session-backends.md` | Deliverable | all | Protocol bundle (session backend interface): how a runtime creates, shows, rings, probes and stops role sessions |
| `docs/runtimes/session.md` | Deliverable | all | Protocol bundle (runtime binding): proposed single-session binding and declared contract gaps (#340) |
| `docs/runtimes/tmux.md` | Deliverable | tmux | Protocol bundle (runtime binding): tmux binding and `crew` usage |
| `docs/scheduling.md` | Deliverable | tmux | Protocol bundle (runtime binding): crew-wide scheduler design for the tmux binding ([#587](https://github.com/mw-ding/eng-crew/issues/587)) |
| `docs/self-improve.md` | Deliverable | all | Protocol bundle (core): the text roles load and cite |
| `docs/specs/**` | Internal | n/a | Maintainer docs: specs and planning, not loaded by roles |
| `docs/verification.md` | Deliverable | all | Protocol bundle (core): the text roles load and cite |
| `examples/**` | Internal | n/a | Worked example: referenced, not installed |
| `packs/github/**` | Deliverable | all | Pack: GitHub capability declaration |
| `profiles/default.toml` | Deliverable | grok-bot | Profile: default profile (spec P7) |
| `profiles/tmux.toml` | Deliverable | tmux | Example profile: tmux example profile |
| `roles/eng.toml` | Deliverable | tmux | Domain registry: engineering role metadata loaded by the tmux runtime |
| `scripts/README.md` | Deliverable | all | Script usage: script guide and guard rules; each script's own usage is its module docstring, printed by `--help` |
| `scripts/changelog-cut.py` | Internal | n/a | Guards and tests: release tooling, run by the release workflow, not installed |
| `scripts/check-changelog-pr.py` | Internal | n/a | Guards and tests: PR fragment requirement, run by CI, not installed |
| `scripts/check-repo.py` | Deliverable | all | Install CLI: the repo guard; `crew-config.py` imports its secret-scan patterns ([#275](https://github.com/mw-ding/eng-crew/issues/275)) |
| `scripts/check-skill-drift.py` | Deliverable | all | Drift check: render-vs-live check ([#128](https://github.com/mw-ding/eng-crew/issues/128)) |
| `scripts/crew` | Deliverable | all | Runtime CLI: crew entry point, including bootstrap and doctor |
| `scripts/crew-config.py` | Deliverable | all | Install CLI: validate and resolve a profile; imports the secret-scan patterns of `check-repo.py` ([#275](https://github.com/mw-ding/eng-crew/issues/275)) |
| `scripts/crew-herdr.py` | Deliverable | tmux | Runtime CLI: local herdr session adapter |
| `scripts/crew-permit.py` | Deliverable | all | Runtime CLI: away permission hook, checker and owner install ([#646](https://github.com/mw-ding/eng-crew/issues/646)) |
| `scripts/crew-precheck.py` | Deliverable | all | Role helper: check enabled builder pre-review markers at head |
| `scripts/crew-render.py` | Deliverable | all | Install CLI: render briefs from the resolved profile |
| `scripts/crew-repo.py` | Deliverable | all | Install CLI: shared GitHub repository checks and dry-run fixers |
| `scripts/crew-roles.py` | Deliverable | all | Install CLI: validate a domain role registry |
| `scripts/crew-tmux.py` | Deliverable | tmux | Runtime CLI: the tmux adapter |
| `scripts/crew.d/**` | Deliverable | all | Runtime CLI: per-command modules ([#224](https://github.com/mw-ding/eng-crew/issues/224)) |
| `scripts/crew_testlib.py` | Internal | n/a | Guards and tests: shared test fixtures |
| `scripts/deliverables.txt` | Internal | n/a | Guards and tests: the manifest this inventory is generated from |
| `scripts/evidence-cli.py` | Deliverable | all | Role helper: capture CLI evidence pairs mechanically ([#652](https://github.com/mw-ding/eng-crew/issues/652)) |
| `scripts/fixtures/**` | Internal | n/a | Guards and tests: test inputs |
| `scripts/flavor-suggest.py` | Deliverable | all | Role helper: offline flavor signals and owner-decided suggestions |
| `scripts/intake-sweep.py` | Deliverable | all | Role helpers: builder and coordinator helpers |
| `scripts/item-flavor.py` | Deliverable | all | Role helper: item rigor records, defaults and lowering reasons |
| `scripts/metrics-decide.py` | Deliverable | all | Role helpers: builder and coordinator helpers |
| `scripts/metrics-refresh.py` | Deliverable | all | Role helpers: builder and coordinator helpers |
| `scripts/release-bundle.py` | Internal | n/a | Guards and tests: release tooling, run by the release workflow, not installed |
| `scripts/release-check.py` | Internal | n/a | Guards and tests: release tooling, run by the release workflow, not installed |
| `scripts/release-trigger.py` | Internal | n/a | Guards and tests: release tooling, run by the release workflow, not installed |
| `scripts/required-docs.txt` | Internal | n/a | Guards and tests: required docs and sections, run by CI |
| `scripts/run-tests.py` | Internal | n/a | Guards and tests: parallel test runner, run by CI, not installed |
| `scripts/step-summary.py` | Deliverable | all | Role helpers: builder and coordinator helpers |
| `scripts/test-*.py` | Internal | n/a | Guards and tests: run by CI and release validation, not installed |
| `templates/README.md` | Deliverable | all | Templates: evidence adapters, product README seed, cards and step lines |
| `templates/backends/github.toml` | Deliverable | all | Render input: `<op:...>` command mapping |
| `templates/backends/slack.toml` | Deliverable | tmux | Render input: away-only Slack notify and recorded GitHub asks |
| `templates/evidence/**` | Deliverable | all | Templates: evidence adapters, product README seed, cards and step lines |
| `templates/flavor-suggestion-issue.md` | Deliverable | all | Template: owner-decided flavor suggestion issue |
| `templates/handoff-manifest.md` | Deliverable | all | Template: runtime handoff manifest that `crew handoff manifest` fills ([#211](https://github.com/mw-ding/eng-crew/issues/211)) |
| `templates/intake-candidate.md` | Deliverable | all | Templates: evidence adapters, product README seed, cards and step lines |
| `templates/metrics-regression-issue.md` | Deliverable | all | Templates: evidence adapters, product README seed, cards and step lines |
| `templates/owner-return-brief.md` | Deliverable | all | Template: standalone owner return brief for recorded away mode |
| `templates/product-readme.md` | Deliverable | all | Templates: evidence adapters, product README seed, cards and step lines |
| `templates/runtimes/grok-bot/**` | Deliverable | grok-bot | Render input: routines and trigger JSON, rendered at install |
| `templates/runtimes/session/**` | Deliverable | all | Template: paste-ready coordinator-session brief until the session binding exists |
| `templates/runtimes/tmux/**` | Deliverable | tmux | Render input: coordinator and role briefs, rendered at install |
| `templates/step-summary.md` | Deliverable | all | Templates: evidence adapters, product README seed, cards and step lines |
| `templates/triage-flavor.md` | Deliverable | all | Template: coordinator item rigor record and lowering reason |

<!-- inventory:end -->

Coordinator session helpers are not in the repo yet; they become
deliverables once upstreamed ([release.md](release.md#upstreaming-the-session-tooling)).

Issue templates: none exist yet (no `.github/ISSUE_TEMPLATE/`). Product-repo
issue templates would be deliverables under `templates/`; this repo's own
stay internal with `.github/**`.

A new tracked path must be classified when it lands: the manifest is the
machine-readable source of this table, and the bundle build and the repo guard
fail on an unclassified path ([release.md](release.md#follow-up-issues)).

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
  smallest allowed bump; the release approver checks the cut PR's version
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
