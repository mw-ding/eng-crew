# eng-crew

eng-crew is a versioned, reviewed rulebook for running a GitHub repo with a
small crew of bots. Each bot has one job: coordinate, build, review and
validate, or merge. Together they take an issue from spec to merged PR with
CI, evidence and a human-readable trail at every step. It exists because
"let an AI write code" falls apart without clear roles, gates and a record of
who did what; this repo writes those rules down and keeps them testable.

New here? Start with the [Quickstart](#quickstart-tmux): zero to a running
tmux crew in seven steps.

## How it works

A coordinator turns a spec into issues with numbered acceptance criteria. A
builder picks each issue up and opens a PR with evidence. CI runs. A reviewer
and validator, a different identity from the author, post a verdict. When the
gate passes, the synthesizer merges and the coordinator closes out. Loops are
capped, and every handoff is a marker on the PR.

![eng-crew collaboration flow](docs/diagrams/eng-crew-flow.png)

*Crew collaboration flow.* Editable source:
[eng-crew-flow.excalidraw](docs/diagrams/eng-crew-flow.excalidraw)
(see [docs/diagrams/README.md](docs/diagrams/README.md)).

- Stages, markers, rounds and the merge gate: [docs/protocol.md](docs/protocol.md)
- Roles, tiers and engines: [docs/roles.md](docs/roles.md)

## Who it's for

- Maintainers who want bots to build and review changes in their repo without
  giving up a merge gate.
- Engineers adopting the crew on a new repo, via the
  [onboarding runbook](docs/runbook-new-repo.md).

## What you get

- A staged protocol with typed evidence, review rounds and a merge gate.
- Routine and listener templates per role, with placeholders only
  ([templates/](templates/README.md)).
- A seed README for product repos ([templates/product-readme.md](templates/product-readme.md)).
- Guard scripts that scan for secrets and check docs and links in CI.
- A lessons log and a changelog of every change.
- Versioned releases of the installable parts: what ships, how it is
  versioned and what each version promises is in
  [docs/deliverables.md](docs/deliverables.md); how a release is cut is in
  [docs/release.md](docs/release.md). Install a tagged version from
  [GitHub Releases](https://github.com/mw-ding/eng-crew/releases), as in
  [Install](#install).

## Quickstart (tmux)

Zero to a running local crew. Each step links to the runbook for depth;
the [tmux binding](docs/runtimes/tmux.md) owns every command's exact
behaviour. `<project>` is a clone of your target repo, `<eng-crew>` the
extracted bundle, and `crew` below means `<eng-crew>/scripts/crew`.

1. **Install and verify** the release bundle: [Install](#install) steps 1 to 4.
2. **Write `crew.toml`** at `<project>/crew.toml` from
   [profiles/tmux.toml](profiles/tmux.toml) plus `[repo]` and real `[paths]`
   ([Set up the target repo](docs/runbook-new-repo.md#set-up-the-target-repo)),
   then check it:
   `python3 <eng-crew>/scripts/crew-config.py validate <project>/crew.toml`.
   Create the `crew:*` labels
   ([Step 1](docs/runbook-new-repo.md#step-1-create-the-crew-labels)) and
   make sure a CI check runs on every PR.
3. **Bootstrap:** `export CREW_PROJECT=<project>/crew.toml` (absolute), then
   `crew bootstrap --project "$CREW_PROJECT" --dry-run`;
   review it and run it again without `--dry-run`
   ([Bootstrap](docs/runbook-new-repo.md#bootstrap-recommended)).
4. **Start:** `crew up --project "$CREW_PROJECT"`. It
   renders the briefs and starts the session with `ash` and the enabled
   leads (table below).
5. **Trust, once, per harness.** A Claude Code `ash` waits at its
   folder-trust dialog (`crew status` shows `ambiguous`): run
   `crew attach ash --rw --project "$CREW_PROJECT"` and accept it; never press a blind
   Enter, which picks `No, exit`. That one answer covers the role worktrees.
   Codex windows are pre-trusted per process, but `crew up` refuses until
   every hook in your host Codex config is trusted once in plain `codex`.
   Pi, Cursor and Muse: see each
   [harness adapter](docs/runtimes/harness-adapters.md)'s trust row.
6. **First issue:** open an issue with numbered acceptance criteria, label it
   `crew:ready` and assign it, or ask `ash` in window 0 to file one. `ash`
   hands it to the builder lead and the pipeline runs; you give the merge-ok
   ([Owner duties](docs/runbook-new-repo.md#run-the-crew)).
7. **Watch and stop:** `crew status --project "$CREW_PROJECT"` (one row per
   window with its liveness), `crew attach <window> --project "$CREW_PROJECT"`
   (read-only without `--rw`), and `crew down --project "$CREW_PROJECT"` to stop every window
   and the session. Problems:
   [tmux troubleshooting](docs/runbook-new-repo.md#tmux-troubleshooting).

### Bringing up the team

Default profile names; window indexes from the
[tmux binding](docs/runtimes/tmux.md#layout-and-naming). See any window with
`crew status`, and look or type with `crew attach <window>` (`--rw` to type).

| Role | Window | Started by |
|---|---|---|
| Coordinator | `ash` (0) | `crew up` |
| Builder lead | `ben-lead` (2) | `crew up`, unless the [launch topology](docs/runtimes/tmux.md#launch-topology) or `--coordinator-only` says otherwise |
| Reviewer lead | `vera-lead` (3) | `crew up`, same exception |
| Builder | `ben-<issue>` (10–19) | The builder lead, when `ash` hands it a ready issue and the scheduler admits it; fix rounds reuse the window |
| Reviewer-validator | `vera-<pr>-r<k>-<pass>` (20–29) | The reviewer lead, one fresh window per review, validate or recheck pass once CI is green at head |
| Synthesizer | `sam` (1) | `ash`, with `crew spawn synthesizer` at the first land; it then stays for the session |
| Researcher | `riley-<issue>` (40–44) | `ash`, per research request or triage sweep; closed after its `done:` |

## Install

1. **Needs:** Python 3.11+, and `gh` logged in (it downloads the release;
   the repo is public, so the assets are also on the
   [Releases](https://github.com/mw-ding/eng-crew/releases) page). The tmux
   runtime also needs tmux.
2. **Download and verify** the latest release (to pin a version, pass its
   tag: `gh release download vX.Y.Z ...`):

   ```bash
   gh release download -R mw-ding/eng-crew --pattern 'eng-crew-*.tar.gz' --pattern SHA256SUMS -D eng-crew-release
   cd eng-crew-release && shasum -a 256 -c SHA256SUMS  # Linux: sha256sum -c SHA256SUMS
   ```

3. **Extract:** `tar -xzf eng-crew-*.tar.gz`. The `eng-crew-<version>/`
   directory is `<eng-crew>` in the runbook, and its `VERSION` file
   (`cat eng-crew-<version>/VERSION`) is the version to record
   ([release.md: Update path](docs/release.md#update-path)).
4. **Check the tools run:**
   `python3 eng-crew-<version>/scripts/crew-config.py validate eng-crew-<version>/profiles/default.toml`
   and `eng-crew-<version>/scripts/crew --help`.
5. **Next:** write `crew.toml` and continue at the runbook's
   [Step 0](docs/runbook-new-repo.md#step-0-write-validate-and-render-the-profile)
   (Grok Bot) or its [tmux runtime](docs/runbook-new-repo.md#tmux-runtime)
   section. Upgrades follow [release.md: Update path](docs/release.md#update-path).

The `v2.0.0` bundle lacks a file the install CLI needs, so step 4 fails on it;
use a release with the [#275](https://github.com/mw-ding/eng-crew/issues/275) fix.

tmux users upgrading to 2.1: read the "Upgrade note (2.1)" entry in the
[release notes](https://github.com/mw-ding/eng-crew/releases) and the
runbook's [tmux prerequisites](docs/runbook-new-repo.md#tmux-prerequisites).

## Status

- **v1 cut: M1–M12 closed** (harness loop through the `AGENTS.md` thin review
  posture), locked 2026-10-29 and released as
  [`v1.0.0`](https://github.com/mw-ding/eng-crew/releases/tag/v1.0.0).
- **M13 configurable core (profiles, renderer, packs): done**, except the
  live box-skill sync ([#140](https://github.com/mw-ding/eng-crew/issues/140)).
- **M14 and M14.1 tmux crew runtime: done.** Binding:
  [docs/runtimes/tmux.md](docs/runtimes/tmux.md); operator steps: the
  runbook's [tmux runtime](docs/runbook-new-repo.md#tmux-runtime) section.
- **M14.2 tmux usability (firstmate defaults): done.**
- **M14.3 tmux polish: done** (#301, #303, #312, #270, #262).
- **R1 versioned release: done**, with
  [`v2.0.0`](https://github.com/mw-ding/eng-crew/releases/tag/v2.0.0) and
  [`v2.0.1`](https://github.com/mw-ding/eng-crew/releases/tag/v2.0.1)
  released.
- Per-slice status: [docs/specs/portable.md](docs/specs/portable.md) §5. See
  also [CHANGELOG.md](CHANGELOG.md) and the
  [closed milestones](https://github.com/mw-ding/eng-crew/milestones?state=closed).
- **Out of cut / held:** the Sam-only merge ruleset
  ([#80](https://github.com/mw-ding/eng-crew/issues/80), needs GitHub Pro or an
  App; stays on `crew:hold`), and the product prove-it apps (they live
  elsewhere, not in eng-crew).
- **Canonical heading:** the
  [Personal AI swarm harness brief](https://www.notion.so/408223c9b3db81809f9bfe3985251c8b)
  is the gap-table north star. It is not a second source of truth for protocol
  text: the repo docs win for normative crew rules.

Content is built by the crew itself through the normal PR pipeline; every
change is recorded in `CHANGELOG.md`.

## More

- Spec: [docs/specs/framework.md](docs/specs/framework.md)
- Lessons log: [docs/lessons/](docs/lessons/README.md)
- Changes: [CHANGELOG.md](CHANGELOG.md) · Process: [CONTRIBUTING.md](CONTRIBUTING.md)
- No secrets or tokens are ever committed here. Per-repo specifics are templates
  with placeholders.
