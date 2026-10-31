# Changelog

All notable changes to this repo are recorded here, in the style of
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Every PR adds an entry
(spec R5: date, PR number, summary) and says whether the box skill copy was mirrored (spec R4). See
[CONTRIBUTING.md](CONTRIBUTING.md).

## [Unreleased]

### Added

- Release bundle attached: in `.github/workflows/release.yml` the `validate`
  job runs `scripts/release-bundle.py "$VERSION"` at the validated SHA,
  checks `SHA256SUMS` with `sha256sum -c`, and uploads
  `eng-crew-<version>.tar.gz` and `SHA256SUMS` as the `release-bundle`
  artifact, replacing the `TODO(#236)` placeholder; the pull request dry run
  builds it for the simulated version. The `publish` job downloads the
  artifact and attaches both files to `gh release create --verify-tag`. No
  other workflow behaviour changes. `crew:sensitive`: the owner approves the
  merge per PR. Roadmap R1.7. (issue #246, PR #248, 2026-10-30) Box skill
  copy: none.
- Release bundle build: `scripts/release-bundle.py <version>` builds
  `eng-crew-<version>.tar.gz` (the paths `scripts/deliverables.txt` classifies
  `deliverable`, at their repo paths under one top-level
  `eng-crew-<version>/` folder, plus `VERSION`) and `SHA256SUMS`,
  deterministically (sorted entries, fixed mtime from `SOURCE_DATE_EPOCH` or
  the commit time, uid/gid 0). Relative links from bundled Markdown to
  internal paths are rewritten to the file at the `v<version>` tag (`raw/`
  URLs for images, so they render inline), then an
  offline link check runs on the bundle. Tests in
  `scripts/test-release-bundle.py`, run in CI. Attaching the bundle in
  `release.yml` is a separate `crew:sensitive` PR. Roadmap R1.6. (issue #236,
  PR #245, 2026-10-30) Box skill copy: none.
- Release workflow: `.github/workflows/release.yml`, dispatched on `main`
  with `version` and `dry_run` (default `true`). A read-only `validate` job
  runs the repo guard, every `scripts/test-*.py` (render parity included),
  markdownlint, the link check and the new `scripts/release-check.py`
  (`[Unreleased]` empty, top section `[<version>]`, tag new and greater than
  the latest), and uploads the notes; pull requests touching the release
  files run it as a dry run on a simulated cut. The `publish` job, behind
  the `release` environment and only with `dry_run=false`, creates the
  annotated tag `v<version>` and the GitHub Release; it never commits, and
  refuses unless the actor is the `RELEASE_OWNER` repository variable (a
  stopgap: GitHub Free private repos have no required reviewers). Bundle
  step left as a placeholder for #236. New release gate row in the
  `docs/protocol.md` gate registry (guards publishing, not merging; no
  fail-open, only defer or cancel). Tests in `scripts/test-release-check.py`,
  run in CI. Roadmap R1.3. (issue #218, PR #243, 2026-10-30) Box skill
  copy: deferred to #140.
- Deliverables manifest: `scripts/deliverables.txt` is the machine-readable
  copy of the `docs/deliverables.md` inventory (#229), one
  `glob<TAB>class<TAB>runtime` row per line. A new `check-repo.py` check,
  `deliverables`, fails on a tracked path that matches no row
  (`unclassified`) or more than one row (`double-classified`).
  `scripts/changelog-cut.py`, not in the #229 table, is classified internal.
  Tests in `scripts/test-check-repo.py`. Roadmap R1.5. (issue #235, PR #242,
  2026-10-30) Box skill copy: none.
- tmux crew watcher hardening, from the #139 dry run (B1, F10, F11, F12):
  `scripts/crew watch` runs each `--source` with a timeout of one scan
  interval (killed and queued as a `source-timeout` wake), so a looping
  source no longer wedges it; sources are documented as one-shot
  (`crew poll --once`). It also wakes when `wake/queue.jsonl` grows (byte
  offset in `watch-state.json`), so a `crew poll` loop in its own window
  works, and ignores the stdout of a source that queued its own records, so
  poll events are queued once. New `crew drain` prints and empties the
  queue under `wake/queue.lock`, which every append takes, so no concurrent
  record is lost. SIGTERM / SIGINT remove `watcher.pid` and save
  `watch-state.json`, which is now saved after every scan. Tests in
  `scripts/test-crew.py`. Roadmap 14.1a. (issue #230, refs #139, PR #241,
  2026-10-30) Box skill copy: none.
- Deliverables and versioned release (design, R1.1): `docs/deliverables.md`
  classifies every path as deliverable or internal (runtime, source or
  generated), packages one bundle per release rendered at install, and sets
  SemVer rules (what is breaking: gates, marker fields, state tags, profile
  keys, pack and interface operations, CLI flags and output, placeholders),
  the compatibility promise to packs and installs, and the first versions
  (`v1.0.0` retro-tag of M12, `v2.0.0` after M14). `docs/release.md`
  designs the release: manual dispatch, the CHANGELOG cut as a normal PR,
  validate and build, owner approval through a protected environment, tag
  and GitHub Release, a draft release-gate row (fail-open: none), rollback,
  the pull-only update path and the session-tooling helpers to upstream.
  Spec P9 and layout rows in `docs/specs/portable.md`; README "What you
  get" points at it. (issue #145, PR #229, 2026-10-30) Box skill copy: none.
- CHANGELOG cut: `scripts/changelog-cut.py <version>` turns `## [Unreleased]`
  into `## [x.y.z] - YYYY-MM-DD` (default today in UTC, `--date` to pin it,
  `--dry-run` to print only), keeps its subsections and entries byte for
  byte and leaves an empty `## [Unreleased]` above. It refuses an empty
  Unreleased, a non-SemVer version, an existing version and a version not
  greater than the latest, leaving the file untouched. Tests in
  `scripts/test-changelog-cut.py`, run in CI. Roadmap R1.2. (issue #217,
  PR #228, 2026-10-30) Box skill copy: none.
- tmux crew watcher: `scripts/crew watch` is the zero-token watcher
  (`docs/runtimes/tmux.md` Q1). It writes `wake/watcher.pid`, blocks on
  new role status lines, runs that probe `dead` / `missing` or stay silent
  past `--stale` (default 15 min), and `--source` event commands (the
  `crew poll` hook), appends each wake to `wake/queue.jsonl`, and exits
  with one reason line so the coordinator is re-invoked. A stale wake says
  `restart` only for a first `dead` / `missing` run and `escalate`
  otherwise. It also types `wake: watcher` into an idle coordinator
  (`--no-nudge` to turn off), and a backstop wake's interval doubles while
  nothing is in flight. `crew restart` no longer loses unlanded work
  (#172): a dead or missing run with unlanded work is relaunched in its own
  worktree, brief and claim instead of being killed and respawned fresh.
  Fake-clock and fake-tmux tests in `scripts/test-crew.py`. Part 2 of 2. (issue #135, PR #222, 2026-10-30)
  Box skill copy: none.
- Render-vs-live drift mode: `scripts/check-skill-drift.py --project
  <crew.toml>` renders the profile with `crew-render.py` and compares every
  rendered file with the same path under the live copy dir (`--live-dir`,
  `ECREW_LIVE_DIR`, else the new optional profile key `paths.live_dir`),
  per section with the existing OK / WORDING / DRIFT classification; a
  rendered file missing from the live copy, an absent or placeholder live
  dir, or a failed render is exit 2, and a live file the render does not
  produce is `EXTRA`. Tests on the render fixtures (match, wording, drift,
  missing, extra, path sources) in `scripts/test-check-skill-drift.py`.
  PR (a) of two; the mirror gate change follows. (issue #128, PR #226,
  2026-10-30) Box skill copy: none.
- tmux role briefs: `templates/runtimes/tmux/{coordinator,builder,reviewer,synthesizer}.md`
  tell each window how to work in this runtime: the coordinator drains the
  wake queue, routes by `crew spawn` / `crew send` / `crew kill`, keeps the
  watcher armed and never pastes payloads; the builder keeps its window for
  the issue, takes fix rounds from its inbox with `ack: <id>` and writes
  `done:` / `blocked:` to `$CREW_STATUS`; the reviewer-validator runs one
  pass in a fresh session, writes its verdict file and `done:`, then exits;
  the synthesizer lands serially under `flock`. They render from the new
  example profile `profiles/tmux.toml`; golden files in
  `scripts/fixtures/render/tmux/`. `crew up --inputs` now defaults to
  `templates/`, and `crew up` / `crew spawn` fall back to
  `render/runtime/<role>.md` when no core brief is rendered. (issue #137,
  PR #225, 2026-10-30) Box skill copy: deferred to #140.
- tmux crew liveness: `crew spawn` records the run identity (pane id, pane
  pid and that process's start time) and its spawn arguments in
  `runs/<window>.json`; `scripts/crew status` prints window, role, item,
  head, heartbeat age, liveness and last status line per run, where
  liveness is the C5 probe from tmux and `ps` (`missing` on any identity
  mismatch, so a new window with the same name and harness is never
  `alive`; `dead` on a dead pane; `alive` when `claude` / `codex` is the
  pane command or a foreground process; otherwise `ambiguous`, `node`
  included); `scripts/crew restart <window>` restarts only a `dead` or
  `missing` run, only once, never a finished one; `crew up` on a dead
  session rebuilds `ash` from disk and lists the recorded runs without
  respawning them. Tests with a fake `tmux` and a fake `ps` in
  `scripts/test-crew.py`; usage in `docs/runtimes/tmux.md`. Part 1 of 2;
  the watcher follows. (issue #135, PR #220, 2026-10-30) Box skill copy:
  none.
- tmux crew serial land and caps: `scripts/crew land-lock acquire|release`
  takes a fail-fast `flock` on `locks/merge.lock`, held by a detached
  holder until release, so a second land fails fast and `crew down`
  refuses meanwhile. `crew spawn` beyond the band cap
  (`runtime.options.builders`, default 5; `runtime.options.reviewers`,
  default 2) creates no window and appends the request to
  `spawn-queue.jsonl`, printing `queued:`; `crew dequeue` spawns the oldest
  queued request whose band has a free slot. Tests in
  `scripts/test-crew.py`; usage in `docs/runtimes/tmux.md`. (issue #136,
  PR #215, 2026-10-30) Box skill copy: none.
- tmux crew CLI: `scripts/crew poll [--once]` is the GitHub wake source:
  read-only `gh` JSON for open crew PRs (head SHA, CI rollup, verdicts
  from hidden `crew:v1` lines at head, merged or closed) and assigned
  `crew:ready` issues is diffed against `poll-state.json` by a pure
  decision function, and each change becomes one wake record in
  `wake/queue.jsonl` naming one consumer (ci-passed → reviewer, ci-failed
  or changes → builder, approved → synthesizer, merged or closed →
  coordinator, newly assigned ready issue → builder). The first run
  records a baseline only. New profile option
  `runtime.options.poll_interval` (default 60). Tests on recorded `gh`
  JSON fixtures in `scripts/fixtures/poll/` and a fake `gh` in
  `scripts/test-crew.py`; usage in `docs/runtimes/tmux.md`. (issue #134,
  PR #223, 2026-10-30) Box skill copy: none.
- tmux crew observe: `scripts/crew attach <window>|<role>` attaches
  read-only by default (`tmux attach-session -r`; `--rw` to type), and
  `crew attach builders` opens a temporary tiled view of the builder band in
  a separate session (one `capture-pane` snapshot pane per builder window),
  killed on detach, so no crew window moves. `scripts/crew logs <window>
  [-n N] [-f]` tails the newest `.crew/runs/**/summary.md` in the run's
  worktree, never raw logs. `docs/observe.md` gains a tmux section that
  replaces the deferred-attach note; usage in `docs/runtimes/tmux.md`; tests
  with the fake `tmux` in `scripts/test-crew.py`. (issue #138, PR #216,
  2026-10-30) Box skill copy: none.
- tmux crew CLI: `scripts/crew send <window> <kind> <ref>...` messages a
  role window by reference: it refuses anything but refs (issue or PR
  number, full SHA, https link, path; no whitespace, no diff or traceback
  markers, 1024-byte line cap), appends one JSON line `{id, kind, refs,
  from, ts}` to `inbox/<window>.jsonl` and types the fixed nudge
  `inbox: <msg-id>` through the tmux adapter. Delivery is proven only by
  `ack: <msg-id>` in the window's status file: `--wait-ack <secs>` or
  `crew acked <window> <msg-id>`. Tests with the fake `tmux` in
  `scripts/test-crew.py`; usage in `docs/runtimes/tmux.md`. (issue #133,
  PR #214, 2026-10-30) Box skill copy: none.
- tmux crew CLI: `scripts/crew spawn <role> --issue <n> | --pr <n>
  [--pass build|fix|review|validate|land]` creates a role window in the
  repo's session at the next free index of its band (`ben-<issue>`,
  `vera-<pr>-r<k>-<pass>`, `sam`), in a unique worktree
  `<worktree-root>/<n>-<sha7>-<role>-<pass>/` from a fresh fetch (refusing
  the primary checkout and existing paths), with engine, model and effort
  from the profile tier routing (a reviewer skips the PR's `Engine:`
  trailer engines), `CREW_*` env via `-e` and the login `CREW_IDENTITY`
  only (the token is derived inside the window), a per-run brief, an atomic
  claim and a run record; Codex is pre-trusted per worktree, and a window
  whose harness is not in the foreground within the timeout is reported
  `failed:` and cleaned up. `scripts/crew kill <window>` stops the window
  and removes only that run's worktree, build output and state files;
  `crew down` now calls it for each role window. Tests with a fake `tmux`
  and a temp git repo in `scripts/test-crew.py`; usage in
  `docs/runtimes/tmux.md`. (issue #132, PR #171, 2026-10-30) Box skill
  copy: none.
- Grok Bot templates as render inputs, with a parity check: `templates/` is
  now the renderer's default `--inputs` tree (`runtimes/grok-bot/`, plus the
  new `backends/github.toml` command mapping for every operation, from
  `docs/backends/github.md` Interface mapping); `crew-render.py` renders
  briefs only when the tree has a `core/` directory and keeps the templates'
  remaining run-time placeholders verbatim. `scripts/test-render-parity.py`
  (run in CI) renders `profiles/default.toml`, alone and with the
  agentconnect example values, and diffs each template against its
  pre-conversion text (`scripts/fixtures/parity/pre/`); a seeded one-word
  drift fails. The `templates/README.md` placeholder table gains a "Profile
  key" column. No template text changes. (issue #126, PR #169, 2026-10-30)
  Box skill copy: deferred to #140.
- tmux crew CLI: `scripts/crew up --project <crew.toml> --inputs <dir>`
  resolves a `runtime.name = "tmux"` profile, renders the briefs into
  `<state-dir>/<owner>__<repo>/render/` and starts the detached session
  `crew-<owner>-<repo>` with the coordinator engine (Claude Code or Codex) in
  window 0 pointed at its brief; `GH_TOKEN` is derived inside the window,
  never in argv or a file. `up` on a running session changes nothing. For a
  Claude Code coordinator it installs the turn-end guard (`crew guard`, a
  Stop hook in the project's `.claude/settings.local.json`); the Codex
  recipe is documented. `crew down` refuses while the land lock is held,
  then kills role windows and the session. All tmux calls go through
  `scripts/crew-tmux.py`; tests with a fake `tmux` in `scripts/test-crew.py`,
  run in CI; usage in `docs/runtimes/tmux.md`. Design credit: firstmate's
  turn-end guard (contract only, no code copied). (issue #131, PR #168,
  2026-10-30) Box skill copy: none.
- Onboarding runbook leads with install by profile: `docs/runbook-new-repo.md`
  gains Step 0 (copy `profiles/default.toml` to `crew.toml`, `crew-config.py
  validate`, `crew-config.py resolve`, `crew-render.py`), maps command
  placeholders to resolved profile keys instead of a placeholder table, keeps
  the GitHub install mechanics (labels, collaborator, milestones and board,
  CI) as Steps 1 to 4 linked from the GitHub backend's Tracking section,
  installs routines from the rendered output with hand-fill as a short
  fallback, and adds checklist rows P1 profile validates, P2 render clean and
  P3 parity (once #126 lands). (issue #129, PR #167, 2026-10-30) Box skill
  copy: none.
- External pack contract and internal-name guard: `docs/packs.md` defines
  the pack layout (`manifest.toml`, optional `profile.toml`, binding docs,
  render overrides), the `eng_crew_version` pin and its compatibility rule,
  the capability declaration and wiring by `resolve --org-profile`, plus the
  direction rule (packs reference eng-crew, never the reverse; also in
  `AGENTS.md`). `check-repo.py --only denylist` fails on a whole-word,
  case-insensitive match of any name in the file named by `CREW_DENYLIST`
  (skipped when unset; no names committed). `crew-config.py resolve` folds
  each backend's `packs/<name>/manifest.toml` capabilities under every
  layer (`# pack:<name>`), and the unsupported-invariant check counts
  undeclared operations as unsupported; manifests accept
  `pack.eng_crew_version`. Tests in `scripts/test-check-repo.py` and
  `scripts/test-crew-config.py`. (issue #127, PR #164, 2026-10-30) Box
  skill copy: none.
- Renderer: `scripts/crew-render.py --project <crew.toml> [--org-profile
  <path>] --inputs <dir> --out <dir>` resolves the profile in-process
  (`crew-config.py resolve`), then writes one brief per role
  (`briefs/<role>.md`) and the profile runtime's artifacts (`runtime/**`)
  from render inputs, replacing install-time `<name>` placeholders from
  profile keys and `<op:<concern>.<operation>>` from a backend command
  mapping. Run-time placeholders stay verbatim. Fails closed with
  `file:line: reason` and writes nothing on an unknown placeholder, missing
  mapping or unsupported capability. Golden-file tests on a fixture profile
  and inputs in `scripts/test-crew-render.py` and `scripts/fixtures/render/`,
  run in CI; usage and placeholder map in `scripts/README.md`. (issue #125,
  PR #163, 2026-10-30) Box skill copy: none.
- Default GitHub profile and pack manifest: `profiles/default.toml` (Grok
  Bot runtime, `github` for all eight concerns, placeholder identities,
  engine routing from `docs/roles.md` Current routing for private repos) and
  `packs/github/manifest.toml` (the GitHub backend's capability declaration,
  every operation `supported`). The schema gains role display names
  (`identities.<role>.name`), `runtime.timezone`, `engines.fallback_engine`
  and `paths.toolchain_bin`; `crew-config.py validate` accepts them and
  validates a pack manifest. Tests in `scripts/test-crew-config.py`. (issue
  #124, PR #161, 2026-10-30) Box skill copy: none.
- Layered config resolver: `scripts/crew-config.py resolve --project
  <crew.toml> [--org-profile <path>]` merges core defaults, the default
  profile (`profiles/default.toml`, when present), an optional org profile
  read by path only and the project file. Tables merge by key; scalars and
  arrays replace; dropping a key under `identities`, `backends` or `engines`
  is an error. The result must pass `validate` plus cross-key checks: the
  unsupported-invariant rule of `docs/interfaces.md`, the single-identity
  `emulated` verdict requirement (#111) and integer options >= 1. Prints
  each key with the layer that set it. Documented in `docs/profile.md`
  (Layers and precedence); tests in `scripts/test-crew-config.py`.
  (issue #123, PR #162, 2026-10-30) Box skill copy: none.
- Profile schema and validator: `docs/profile.md` documents the `crew.toml`
  install-time profile (`[repo]`, `[runtime]` with tmux options,
  `[backends.<concern>]` for the eight interface concerns with an optional
  capability declaration, `[identities]` by `gh_user` login, `[engines]` tier
  routing, `[paths]`): every key, type, default and the placeholder it
  replaces. `scripts/crew-config.py validate <file>` (stdlib `tomllib`)
  prints `file:key: reason` and exits 1 on a missing or unknown key, unknown
  concern, runtime, backend or engine, wrong type, bad capability or a
  token-shaped value (patterns imported from `check-repo.py`); tests in
  `scripts/test-crew-config.py`, run in the CI `repo-guard` job. Indexed in
  `docs/README.md`, pinned in `scripts/required-docs.txt`. (issue #122,
  PR #159, 2026-10-30) Box skill copy: none.
- Backend interfaces (`docs/interfaces.md`): the minimum operations for each
  of the eight concerns (change, review, tracker, state tags, markers, CI,
  events, owner channel), the guarantee of each and the invariant (I1–I5) it
  protects; the capability declaration format (`supported | emulated (how) |
  unsupported`) with the unsupported-invariant rule; and the single-identity
  analysis (I1 breaks; compensation is COMMENT-review verdicts plus a recorded
  owner merge-ok, #111). `docs/backends/github.md` gains an Interface mapping
  section: one `gh` command or API call per operation. Adds no rule, gate,
  cap, marker field or label; `docs/protocol.md` untouched. Indexed in
  `docs/README.md`, pinned in `scripts/required-docs.txt`. (issue #121,
  PR #154, 2026-10-30) Box skill copy: none.
- tmux runtime binding design (`docs/runtimes/tmux.md`): answers #110 Q1
  wake (status files, inbox nudges and `crew poll` feed a zero-token watcher;
  turn-end guard), Q2 lifetime, Q3 coordinator engine, Q5 identities, Q6
  concurrency and Q7 failure (process-identity liveness probe), each with
  alternatives; contract table C1–C8 with C1 and C8 gaps declared; window
  layout with index bands; spawn and kill mechanics from #132. Watcher,
  turn-end guard, delivery-ack and liveness patterns credited to firstmate
  (MIT), no code copied. Indexed in `docs/README.md`, pinned in
  `scripts/required-docs.txt`. (issue #130, PR #152, 2026-10-30) Box skill
  copy: none.
- GitHub backend (`docs/backends/github.md`), section Tracking: the ten
  `crew:*` labels with GitHub colours and descriptions, why no listener fires
  on labels, Milestones and Project (v2) board, `Closes #n` / `Refs #n` /
  `Part of #n` / `Depends on #n` linkage, and the no-issue-comment steering
  limit. Protocol §4, §6, §7 and §9, `architecture.md` (label table kept as the
  role view), the runbook Steps 1 and 3 and `concepts.md` link it. Text move
  only; no rule, gate, cap, marker field or label changes. Indexed in
  `docs/README.md`, pinned in `scripts/required-docs.txt`. (issue #116,
  PR #149, 2026-10-30) Box skill copy: deferred to #140.
- GitHub backend (`docs/backends/github.md`), section Reviews, markers and
  identities: COMMENT vs formal reviews and the events each fires, why bots
  never post plain or inline comments, `gh` identity selection, why GitHub
  refuses self-approve, and the land (`--match-head-commit`) and
  update-branch mechanics. Protocol §1 and §4 keep the rules and link the
  mapping. Text move only; no rule, gate, cap, marker field or label changes.
  Indexed in `docs/README.md`, pinned in `scripts/required-docs.txt`; lesson
  hygiene note in `docs/lessons/2026-10-19-bottlenecks.md`. (issue #115,
  PR #146, 2026-10-30) Box skill copy: deferred to #140.
- Runtime contract (`docs/runtimes/README.md`): eight capabilities every
  runtime provides (wake on event, one consumer per event, messages by
  reference with proof of delivery, status protocol, liveness classes,
  isolation, serial land, owner channel and SLA), each with the guarantee it
  protects, plus a gap-declaration format. Contracts adapted from firstmate
  (`kunchenguid/firstmate`), no code copied (#130 decision).
  `docs/runtimes/grok-bot.md` gains a contract table with gaps declared.
  Pinned in `scripts/required-docs.txt`, indexed in `docs/README.md`.
  (issue #120, PR #148, 2026-10-30) Box skill copy: none.
- Concepts glossary (`docs/concepts.md`): one entry per abstract protocol
  term (change, change head, verdict, narrative post, state tag, marker, CI
  signal, wake event, tracker item / milestone / board, owner channel, land,
  runtime, backend, profile / pack) with its definition, the invariant it
  touches and today's GitHub / Grok Bot mapping. Terms only; no rule moves.
  Linked from `docs/README.md` and the `AGENTS.md` map; pinned in
  `scripts/required-docs.txt`. (issue #113, PR #142, 2026-10-29) Box skill
  copy: none.
- Portable eng-crew spec (`docs/specs/portable.md`): requirements P1–P8
  for runtime and per-concern tool abstraction, install-time profile and
  config layers; invariants every runtime + backend keeps; target layout;
  M13/M14 slices with dependencies; dated decisions from #110, #111, #112
  and #140; open questions mapped to the issues that settle them. Indexed
  in `docs/README.md` and pinned in `scripts/required-docs.txt`.
  (issue #110, 2026-10-29) Box skill copy: none (spec only; no protocol or
  template change).
- Standing quota diversity waive for reviewer engines: prefer available,
  cheap DeepSeek before reset, else allow Codex for one round's verdict
  under the documented risk, identity and recording rules.
  (issue #104, 2026-10-29) Box skill copy: eng-crew-roles (roles) and
  eng-pr-pipeline (protocol) need mirror (coordinator mirrors before merge;
  `crew:needs-mirror` holds the PR until then).
- Coordinator soft-finding follow-up after squash: file and dispatch a
  `crew:ready` issue in the same awake window, unless the user parked softs
  for a named cut; includes an issue template and duplicate check. Softs
  never block §7 squash. (issue #105, 2026-10-29) Box skill copy:
  eng-pr-pipeline (protocol §6) needs mirror (coordinator mirrors before
  merge; `crew:needs-mirror` holds the PR until then).
- Deploy secret sync AC for new deploy milestones: compare shared secrets
  across consuming hosts with safe fingerprints and name the GitHub secret
  store the workflow reads. New-repo wiring records secret names and hosts.
  (issue #103, 2026-10-29) Box skill copy: eng-pr-pipeline (protocol §3)
  needs mirror (coordinator mirrors; `crew:needs-mirror` until mirrored).
- Mutation evidence rule: behaviour-changing PRs that add or change a
  user-visible create, update or complete (or equivalent) mutation paste an
  inline happy-path snippet (create an entity, progress/complete it, then
  delete it: item and/or list delete with cascade, where the snippet also
  shows the child items are gone) in `## Test Output` and
  `## Acceptance Evidence`; the reviewer-validator checks it and reproduces
  where possible, else `disagrees`. Docs-only and non-CRUD PRs unchanged.
  (issue #100, 2026-10-29) Box skill copy: eng-pr-pipeline (protocol §3)
  needs mirror (coordinator mirrors before merge; `crew:needs-mirror` holds
  the PR until then).
- Inline evidence rule for PR bodies: `## Test Output` and `## Acceptance
  Evidence` must paste command → output snippets and/or screenshots;
  path-only `evidence/` pointers are insufficient; `evidence/` stays the
  durable audit trail. Example in protocol §3; roles PR template and
  verification builder duty updated. (issue #98, 2026-10-29) Box skill copy:
  eng-pr-pipeline (protocol §3) needs mirror (coordinator mirrors after
  merge).
- README rewritten for first-time readers: what and why, plain-words how it
  works with the diagram, who it is for, what you get, and the v1 cut block
  kept. (issue #96, 2026-10-29) Box skill copy: no box skill change.
- Product-repo README seed `templates/product-readme.md`, a README install
  step in `docs/runbook-new-repo.md` (Step 6) and a normative README rule in
  `docs/protocol.md` section 8. (issue #96, 2026-10-29) Box skill copy: needed
  for `docs/protocol.md` and `templates/` (`crew:needs-mirror` until mirrored).
- README Status / v1 cut section: M1–M12 closed, in-cut vs out-of-cut (#80
  hold, product prove-its), Notion brief as gap-table north star. (#95,
  issue #94, 2026-10-29) Box skill copy: no box skill change.
- Root `AGENTS.md` thin review/build posture (blocking only for failed ACs,
  stage 7 gate, CI or security; wording and script edge cases are yellow
  follow-ups), required reading in the B1, B2, V1 and V2 templates, and a
  findings entry for the #74/#77/#88 round-burners (#93, issue #92,
  2026-10-29) Box skill copy: eng-pr-pipeline and eng-crew-roles get the "read
  AGENTS.md" line (coordinator mirrors after merge).
- Self-improve intake (M11): `docs/self-improve.md` (triggers, candidate card,
  accept/close, lesson path, `repo:` vs `crew:` scope, risks),
  `templates/intake-candidate.md`, the offline `scripts/intake-sweep.py` helper
  with `scripts/test-intake-sweep.py` (CI step), a weekly intake note in the
  stuck-PR sweeper template, coordinator/builder notes in `docs/protocol.md`
  and `docs/roles.md`, lesson `2026-10-29-self-improve-intake.md` and a
  findings entry. (#90, issue #89, 2026-10-29) Box skill copy:
  eng-pr-pipeline and eng-crew-roles (coordinator mirrors after merge).
- Metrics to decisions: `docs/metrics/decisions.md` (latency and rework
  sensors, windows, tunable thresholds, rollup vs per-repo, the `metrics-gate`
  issue, hold/waiver/lift), `scripts/metrics-decide.py` with fixture tests and
  a CI step, `templates/metrics-regression-issue.md`, gate notes in protocol
  section 6, `docs/roles.md` and the coordinator, builder, reviewer-validator
  and synthesizer templates, lesson `2026-10-29-metrics-to-decisions.md` and a
  findings entry. (#88, issue #86, 2026-10-29) Box skill copy:
  eng-pr-pipeline and eng-crew-roles (Ash mirrors before merge:
  `crew:needs-mirror` blocks the squash until the mirror comment is posted,
  protocol sections 6 and 7).
- Step-summary observe protocol (M8): `docs/observe.md` (when to write a step
  line, fields, `.crew/runs/` paths, promote the short summary onto the PR,
  what reviewers skim, risks), helper `scripts/step-summary.py` with
  `scripts/test-step-summary.py` (run in CI), `templates/step-summary.md`,
  builder, reviewer and synthesizer template notes, protocol §3 and roles
  pointers, `.gitignore` for raw step logs, lesson
  `2026-10-29-step-summary-observe.md` and a findings entry. (#87, issue
  #85, 2026-10-29) Box skill copy: eng-pr-pipeline and eng-crew-roles
  (coordinator mirrors before merge; `crew:needs-mirror` holds the PR until then).
- Verification protocol: typed runtime evidence as a merge gate. New
  `docs/verification.md` (shape table for web, CLI, service, API and mobile;
  docs-only N/A; fail-open), role duties in `docs/roles.md`, protocol §3, §7
  and Gate registry, and the B1, V1, V2 and synthesizer templates; starter
  adapters `templates/evidence/` (CLI exit/stdout, web screenshot); lesson
  `2026-10-29-typed-verify-evidence.md`, findings entry, required-docs pins and
  a `check-repo.py` `verification-shapes` rule with tests. (#84, issue #83,
  2026-10-29) Box skill copy: eng-pr-pipeline and eng-crew-roles (the mirror comment must land and clear `crew:needs-mirror` before merge).
- Synthesizer merge blockers: an open coordinator hold-until-X (or crew hold
  command) overrides standing doc-only merge-ok, and an open `steer cmd=rereview`
  at the current head blocks squash until a fresh `pass=verdict` lands on a
  different engine; protocol §7 and Gate registry, `templates/synthesizer.md`,
  lesson `2026-10-29-synthesizer-hold-race.md`, findings entry, and a
  `check-repo.py` static guard. (#82, issue #81, 2026-10-29) Box skill copy:
  eng-pr-pipeline (Ash mirrors before merge: `crew:needs-mirror` blocks the squash
  until the mirror comment is posted, protocol sections 6 and 7).
- Correction hierarchy in `docs/lessons/README.md` (architecture, types, lint, CI,
  prose last; "prose only, because ..." exception; new `encoded` status) and the
  first encoded lesson: `check-repo.py` rule `marker-sha` fails a `crew:v1` marker
  whose `sha=` is not a full 40-char SHA, with tests. (#77, issue #69,
  2026-10-28) Box skill copy: no box skill change.
- Merge-enforcement runbook with target rules, plan blocker, application,
  verification, rollback and fail-open; protocol §7 and onboarding pointers.
  (#67, 2026-10-28) Box skill copy: mirror needed (docs/protocol.md §7 pointer).
- Cycle-time and rounds metrics artifact: `docs/metrics/` (README, `prs.md`,
  `prs.csv`), `scripts/metrics-refresh.py` and its offline test, and a metrics
  refresh note in the stuck-PR sweeper template. (#75, issue #63,
  2026-10-28) Box skill copy: not mirrored here; templates/ note to be mirrored
  by the coordinator.
- Owner-SLA drill plan: `docs/metrics/owner-sla-drill.md` (synthetic hold, expected
  timestamps, checks, results table; coordinator owns the clock). (#71, issue #66,
  2026-10-28) Box skill copy: no mirror needed (no protocol or template change).
- Gardening findings buffer: `docs/findings/README.md` (how to append a smell,
  when to batch, ownership, entry template) and `docs/findings/buffer.md`
  seeded with the recurring builder B2 watch smell (PRs #35, #38, #41); lessons
  README points to it. (#78, issue #68, 2026-10-28) Box skill copy: no box
  skill change.
- Lessons log: `docs/lessons/README.md` (entry format and index) and
  `docs/lessons/2026-10-19-bottlenecks.md`. Added `CONTRIBUTING.md` (iteration
  process) and this changelog. (#15, 2026-10-20) Box skill copy: no box skill
  change.
- Architecture overview and docs index. (#8, 2026-10-20) Box skill copy: no box
  skill change.
- Crew collaboration-flow diagram. (#10, 2026-10-19) Box skill copy: no box skill
  change.
- Crew protocol doc: `docs/protocol.md` ports the eng-pr-pipeline protocol into
  the repo. (#14, 2026-10-20) Box skill copy: no box skill change.
- Roles, tiers and engines: `docs/roles.md` ports the `eng-crew-roles` box skill.
  (#13, 2026-10-20) Box skill copy: not edited (the doc is a port with no new
  policy).
- Routine and listener templates per role (`templates/`) and AgentConnect
  examples. (#16, 2026-10-20) Box skill copy: no mirror needed (new files only).
- Crew-flow diagram embedded in `docs/architecture.md`. (#22, 2026-10-20) Box skill
  copy: no box skill change.
- Onboarding runbook for a new repo: `docs/runbook-new-repo.md`. (#26, 2026-10-20)
  Box skill copy: no box skill change.
- CI repo guard: `scripts/check-repo.py` checks for secrets, required docs and
  sections, and relative links, with fixture tests. (#17, 2026-10-20) Box skill
  copy: no box skill change.
- Protocol: evidence a reviewer's verdict relies on is committed on the PR head,
  never a side branch; evidence-only changes get a rereview steer
  (`docs/protocol.md` §3, §6). New lessons entry
  `docs/lessons/2026-10-20-evidence-on-pr-head.md`. (#23, issue #19, 2026-10-20)
  Box skill copy: Ash (coordinator) updated the box eng-pr-pipeline skill in
  sync with this change.
- Lesson statuses use one vocabulary (`applied` / `superseded` / `open`) and were
  re-verified against `main`; new drift check `scripts/check-skill-drift.py`
  (with `scripts/test-check-skill-drift.py`) compares `docs/protocol.md` and
  `docs/roles.md` to the box skills, run by the coordinator on
  `crew:needs-mirror` and after protocol/template PRs. (#74, issue #70,
  2026-10-28) Box skill copy: not mirrored here; mirror by the coordinator if
  protocol/templates changed (this change touches neither).

### Changed

- Post-R1 / M14.1 cleanups: `docs/release.md` drops "Nothing here is
  implemented yet" and the "R1.3 adds the row" wording, and names the merged
  workflow, bundle build and bundle attach PRs and the hand-released
  `v1.0.0`; `docs/interfaces.md` single-identity Scope allows an owner
  standing merge grant (the #111 grant) as an alternative to a per-change
  merge-ok, with no gate change; `docs/runtimes/tmux.md` documents
  `paths.eng_crew` next to the other profile paths; and
  `.github/workflows/release.yml` adds `scripts/release-bundle.py` and
  `scripts/test-release-bundle.py` to its `pull_request.paths` filter only.
  `crew:sensitive`: the owner approves the merge. Refs #110, #145, #233.
  (PR #252, 2026-10-30) Box skill copy: none.
- tmux briefs work in any repo (14.1d): every brief cites eng-crew docs as
  `<eng-crew>/docs/...` (new optional profile key `paths.eng_crew`), runs
  `crew` as `$CREW_BIN` and adds `-R <owner>/<repo>` to every `gh` command.
  The builder writes step summaries with `scripts/step-summary.py` to
  `.crew/runs/issue-<n>/build/summary.md` (fix rounds `pr-<pr>/fix-<k>/`).
  The coordinator drains with `crew drain`, arms the watcher with a
  one-shot `crew poll --once` source, starts validation only after the
  review pass says `pass`, and spawns the next round when a builder `done:`
  comes at the round's verdict head. The reviewer's idempotency check is per
  round, and a failing review pass posts the `changes` verdict itself. The
  synthesizer uses `crew land-lock acquire/release` and reads two new tmux
  options: `merge_grant` (standing grant scope, default `"none"`: per-PR
  merge-ok) and `hold_label_blocks` (default `true`); a grant gives
  permission only. Golden render fixtures and tests updated; `scripts/crew`
  docstring marks `--inputs` optional. Grok Bot templates unchanged. Refs
  #139. (issue #233, PR #244, 2026-10-30) Box skill copy: deferred to #140.
- Mirror hold gate is a drift check (#128): for a change touching
  `docs/protocol.md` or `templates/`, the coordinator's mirror comment counts
  only if it records the rendered output deployed to the live dir and
  `check-skill-drift.py --project` (plus `--only pipeline` when
  `docs/protocol.md` changed) exiting 0 at the last touching commit, with the
  commands and output inline. Who, label, lighter-lane exemption and
  fail-open are unchanged. Protocol §6, §7 and Gate registry, Grok Bot
  mirror hold gate, `CONTRIBUTING.md` "Two copies", portable spec P4 and §8,
  `scripts/README.md`, and a lesson. (issue #128, PR #227, 2026-10-30) Box
  skill copy: deferred to #140.
- Protocol preamble, §6, protocol freeze, gate contract, gate registry and §7
  reworded in glossary terms (`docs/concepts.md`): change, change head,
  verdict, narrative post, state tag, CI signal, wake event, tracker item /
  board, land, owner channel, backend. The gate registry gains a **Binding**
  column (core / runtime / backend). Builder watch and mirror hold become
  runtime gates in §7; their Grok Bot satisfaction rules move verbatim to
  `docs/runtimes/grok-bot.md` (Runtime gates). `docs/architecture.md` role
  table column "GitHub identity" is now "Identity", linked to the GitHub
  backend. Lesson hygiene note in the merge-gate watch-race lesson. Anchors
  and the `synthesizer-blockers` guard text are unchanged. No rule, gate, cap,
  marker field or label changes meaning. Closes M13 Phase A. (issue #119,
  PR #155, 2026-10-30) Box skill copy: deferred to #140.
- Protocol hard rules and §1–§5 reworded in glossary terms
  (`docs/concepts.md`): change, change head, verdict, narrative post, state
  tag, marker, CI signal, wake event, tracker item / board, land, owner
  channel, backend. GitHub and Grok Bot specifics stay only where the
  sentence links `docs/backends/github.md` or `docs/runtimes/grok-bot.md`;
  wake event names, labels, marker fields and `APPROVE` / `REQUEST_CHANGES`
  are kept. §1 is now "Roles and identities" (column "Identity"), with the
  old `#1-roles-and-github-identities` anchor kept; §2 stage 3 points to the
  runtime binding for the per-change watch. Lesson statuses re-checked;
  hygiene notes in the evidence-on-head and validation-gate lessons. No rule,
  gate, cap, marker field or label changes meaning. (issue #118, PR #153,
  2026-10-30) Box skill copy: deferred to #140.
- Routine templates moved under `templates/runtimes/grok-bot/` (`git mv`,
  contents unchanged apart from relative-link depth): B1, B2, V1, V2, S1,
  A1–A3, `wiring.md` and `reviewer-engines.md`. Runtime-neutral templates
  (evidence adapters, `step-summary.md`, `product-readme.md`,
  `intake-candidate.md`, `metrics-regression-issue.md`) stay in
  `templates/`. `templates/README.md` indexes both trees; links in docs,
  examples and lessons, `scripts/required-docs.txt` and the
  `synthesizer-blockers` guard path updated. The `crew:needs-mirror` rule
  keys on the `templates/` prefix and still covers the moved files; no rule,
  gate, cap, marker field or label changes meaning. (issue #117, PR #151,
  2026-10-30) Box skill copy: deferred to #140.

- Grok Bot runtime binding (`docs/runtimes/grok-bot.md`): routine-only
  mechanics moved verbatim out of the core. From protocol §6: per-PR watches,
  the verified B2 hand-off, comment-listener wakes and the lighter-lane
  routing paragraph; from the protocol: the pilot notes; from
  `templates/README.md`: event to consuming role, the lighter-lane routing
  note and routine limits. Each source spot keeps a one-line pointer; no
  rule, gate, cap, marker field or label changes meaning. Pinned in
  `scripts/required-docs.txt`, indexed in `docs/README.md`; lesson status
  paths updated. (issue #114, PR #147, 2026-10-30) Box skill copy: deferred
  to #140.

- Builder heartbeat and stuck-PR sweeper watchdog: builder workers refresh a
  `heartbeat:` line in their claim file every 5 min; the sweeper's `builder-silent`
  row flags a claim silent for 15 min and messages the builder. Bottleneck lesson
  #2 marked documented. (#72, issue #65, 2026-10-28) Box skill copy: not mirrored
  here; mirror by the coordinator.
- Templates match the lighter lane's B2/watch and mirror exemptions; reviewer
  verdict-pass messages route REQUEST_CHANGES, and sweeper/coordinator messages
  route red CI and close-out to the builder. Lane membership uses the full
  diff at head; fixes leaving the lane attach B2. Follows up the lighter-lane
  notes (Refs #55). (issue #57, 2026-10-25)
  Box skill copy: not mirrored here; mirror by the coordinator.

- The coordinator owns triage: a window at least once per awake half-day, and
  every open issue leaves it `crew:ready`, `crew:spec`, `crew:needs-md`,
  deferred to the next milestone, or closed with a reason. The stuck-PR sweeper
  promotes `crew:hold` / `crew:escalated` items waiting on the user for more
  than 2h (awake, PT) to `crew:needs-md`, routes nudge-cap escalations through
  the coordinator, skips held and needs-md PRs for stall nudges but lists them,
  and reports open issues with no `crew:*` state label older than one awake
  day. A reviewer-validator that holds its verdict for a user decision adds
  `crew:needs-md` and posts a `pass=hold` COMMENT review with `verdict=n/a`
  naming the open item (folds in #48). (#56, issue #51, 2026-10-25)
  Box skill copy: not mirrored here; mirror by the coordinator.

- Protocol and templates change in milestone batches, with a blocking-gate
  exception governed by a gate contract and registry. The lighter lane for
  non-protocol docs skips B2 and the mirror hold, keeps CI and review/validation,
  and routes fixes to the builder by message. (#55, issue #50, 2026-10-25)
  Box skill copy: not mirrored here; mirror by the coordinator.

- Owner decisions have a 2h awake-hours PT SLA, `crew:needs-md` escalation,
  timed defaults, and asks only through the coordinator. Standing doc-only
  merge-ok (excluding code, `.github/`, `templates/`, and `docs/protocol.md`)
  preserves all other merge gates. Onboarding requires Milestones and a
  Project board; closed milestones are frozen. (#54, issue #49, 2026-10-25)
  Box skill copy: not mirrored here; mirror by the coordinator.

- Merge gate requires the builder's `pass=watch` marker (full 40-char `sha=` of
  any commit on the PR, same rule as the reviewer cross-check) in protocol §7
  and the synthesizer template; a PR without it is held and the synthesizer
  pings the builder with priority. The reviewer's first verdict pings the
  builder with priority (still never creating B2). New lessons entry
  `docs/lessons/2026-10-23-merge-gate-watch-race.md` for the PR #41 hand-off
  race. A PR changing `docs/protocol.md` or `templates/` gets a
  `crew:needs-mirror` label from the reviewer's verdict pass; the merge gate
  refuses to merge while it is present, and the coordinator removes it on
  posting the box-skill mirror comment, then pings the synthesizer (new label in
  the runbook, architecture, wiring and role templates). The gate's external and
  cutover exemptions are now explicit with reasons, plus a third for
  coordinator-opened `crew:spec` PRs (no builder, no B2; merge on `/crew
  merge-ok`). A cutover PR is gated again as soon as its builder posts its watch
  review or any `crew:v1` marker after the cutover (by post time, covering B2
  attached at the unchanged cutover SHA), independent of the marker. The
  reviewer adds `crew:needs-mirror` before posting the verdict, but skips it
  when the coordinator's mirror comment is newer than the last
  protocol/template-touching commit (a later such commit needs a fresh mirror
  comment); the synthesizer uses the same freshness rule, and the synthesizer derives the
  hold from the changed paths, not only the label. (#45, issue #43, 2026-10-23) Box
  skill copy: not mirrored here; mirroring the box eng-pr-pipeline skill is for
  Ash.
- Reviewer watch cross-check accepts a `pass=watch` marker whose full 40-char
  `sha=` is any commit on the PR, not only the head (the marker is posted once
  per PR, so a CI-fix push before the first verdict must not look like a missing
  watch); `<sha7>` wording in the protocol now includes review headers; the
  "Stale known-gap bullet" lessons entry gains its status and linked-issue
  fields. (#44, issue #42, 2026-10-23) Box skill copy: mirror of the box
  `eng-pr-pipeline` skill is for the coordinator (Ash).
- Watch hand-off: the routine folder id is the single identifier written to
  `watches/pr-<n>.b2`; the B1 run only requests the hand-off and the parent turn
  alone verifies, writes the marker file and posts `pass=watch`; every marker's
  `sha=` is the full 40-char head SHA and the reviewer cross-check matches on it.
  Stale #19 known-gap bullet updated. New lessons entry
  `docs/lessons/2026-10-23-watch-handoff-first-run.md`. (#41, issue #39,
  2026-10-23) Box skill copy: mirror of the box `eng-pr-pipeline` skill is for
  the coordinator (Ash).
- `docs/protocol.md` links `docs/roles.md` (and its worktree isolation section)
  directly instead of calling it planned; removed the resolved #29 entry from the
  runbook's known gaps. `docs/README.md` moves `scripts/` to Available now, and
  the Planned section now says nothing is planned. (#40, issue #29, 2026-10-23)
  Box skill copy: no box skill change.
- Aligned the live `crew:needs-md` label description on eng-crew with the runbook
  ("Blocked on an owner decision (recommended default + deadline)") and removed
  the resolved #28 entry from the runbook's known gaps. (#38, issue #28, 2026-10-23)
  Box skill copy: no box skill change.
- Engine-steer example uses the actual-builder-engine wording and links
  `docs/roles.md#actual-builder-engine`. (#35, issue #34, 2026-10-23) Box skill
  copy: no box skill change.
- Merge-ups use no review round: a clean merge-up after an APPROVE gets a formal
  merge-up re-approve with the same round; after CHANGES it gets an ack with no
  round and no verdict; a conflict resolution that changes behavior is a normal
  round. The #16 ack-based merge-gate exception is removed from the reviewer,
  synthesizer and sweeper templates. (#32, 2026-10-21) Box skill copy: the box
  eng-pr-pipeline skill already has this rule; the repo mirrors it.
- Actual builder engine: a round's builder engine is the engine that actually
  wrote its commits, named in the fix note, an `Engine:` commit trailer and the
  builder marker; the reviewer must differ from it. If the builder marker and the
  fix note or commit trailer disagree on the engine, the note or trailer wins,
  and before merge the reviewer re-checks at head (fresh review + validation) on
  an engine different from the actual builder engine, triggered by the
  coordinator's rereview steer. (#33, 2026-10-21) Box skill copy:
  the box eng-pr-pipeline skill already reads the engine that actually wrote the
  round; the eng-crew-roles box skill still needs the mirror (flagged to the
  coordinator).
- Builder per-PR watch B2 attachment is verified and observable: builder parent
  turn lists routines, confirms the four events, records `watches/pr-<n>.b2`
  and posts a `pass=watch` marker; sweeper `no-builder-watch` row and
  detection-window note; reviewer first-verdict cross-check; protocol event
  list and runbook B2 creation point corrected. New lessons entry
  `docs/lessons/2026-10-23-builder-watch-attach.md`. (#37, issue #36,
  2026-10-23) Box skill copy: the box `eng-pr-pipeline` skill mirror (the `watch`
  pass value in §4, B2 events `ci-failed`, `review-changes-requested`,
  `pr-merged`, `pr-closed` in the §6 builder line, and the attach-verification
  step) is applied by the coordinator before merge per R4. AC1 dry run on PR #37
  recorded in the lessons entry.

### Fixed

- tmux crew restart, hooks dialog and state fixes from dry run 2 (#234 N2,
  N3 code side, N4, N5, N7, N8, F15) and the #139 live run (F5, F7):
  `crew restart` of a builder whose last line is `done: #n #pr sha` restarts
  as `--pass fix --pr <pr>`, never a second build pass; the watcher queues a
  `dialog` wake (action `escalate`) on the next scan when a run shows a
  trust or Codex hooks-review dialog, instead of after `--stale`; every
  Codex pass runs `-s workspace-write --add-dir <state-dir>/<owner>__<repo>`,
  so review and validate can write `$CREW_STATUS` and `verdicts/`; `crew
  spawn` adds `.crew/` to the worktree's `info/exclude`; every window gets
  `CREW_PROJECT`; the watcher handles SIGHUP like SIGTERM; the stale wake
  key ignores the liveness class; commands refuse a profile whose
  `state_dir`, `worktree_root` or `toolchain_bin` is still a placeholder;
  `crew kill` removes all of the run's `runs/<window>.*` files. Tests in
  `scripts/test-crew.py`; `docs/runtimes/tmux.md` updated. Roadmap 14.1f.
  (issue #250, refs #139, PR #260, 2026-10-30) Box skill copy: none.
- tmux briefs from dry run 2 (#234 N1, N2 and N3, brief side): the
  coordinator brief never types into a role window on a `dialog` wake or an
  `ambiguous` `stale:` wake; it kills and respawns the window once when its
  launch options should have prevented the prompt, else asks the owner with
  the window name and `crew attach WINDOW --rw`. The builder build pass looks
  for an open PR that closes the issue and adopts it as a fix round instead
  of opening a duplicate. The builder branch is `builder/<n>-<slug>`, not an
  unrendered `<role>/`. Golden fixtures under `scripts/fixtures/render/tmux/`
  updated; Grok Bot renders unchanged. Roadmap 14.1g. (issue #251, refs #139,
  PR #253, 2026-10-30) Box skill copy: deferred to #140.
- tmux crew review rounds, claims and probes from the #139 dry run (B2 code
  side, F3, F4, F7, F17, F18, F20, F21, `verdicts/` cleanup): `crew poll`
  emits `fix-at-head` (to the reviewer, with round `k`) when a builder fix
  note lands at the head of a `verdict=changes`, so an evidence-only fix no
  longer deadlocks round 2, and `ci-passed` records carry the round `k`;
  reviewer claims (`reviewer-pr<n>-<sha7>-r<k>-<pass>`) and worktrees carry
  the round and pass, so review and validate run in parallel; `done:` is
  terminal (no restart, skipped by the watcher) only for reviewer and
  synthesizer runs, so a builder that dies after `done:` is detected and
  restartable; Codex's `Hooks need review` dialog probes `ambiguous`; the
  synthesizer takes the tier's first engine as is; a dead pane reads `dead`
  at spawn, not `export`; `crew kill` removes a reviewer run's verdict
  files. Tests in `scripts/test-crew.py`; `docs/runtimes/tmux.md` updated.
  Roadmap 14.1c. (issue #232, refs #139, PR #247, 2026-10-30) Box skill
  copy: none.
- tmux crew process, env and safety fixes from the #139 dry run:
  `crew kill` and `crew down` SIGTERM the pane's process group, SIGKILL
  what is left after 2 s and check it is gone (Codex ignores the SIGHUP of
  `kill-window`); `crew guard` is a no-op unless `CREW_ROLE=coordinator`,
  so the project Stop hook no longer blocks role windows; a Codex
  coordinator is pre-trusted for the project, and a Claude Code trust
  dialog is documented and probes `ambiguous` in `crew status`, which now
  has a coordinator row; `CREW_SANDBOX_ENV` reaches every window, not only
  Codex role windows; `crew up` prints render output only on failure; every
  window gets `CREW_BIN`, the absolute path of this checkout's
  `scripts/crew`. (issue #231, refs #139, PR #240, 2026-10-30) Box skill
  copy: none.
- `crew kill` refuses to remove unlanded work: before removing a run's
  worktree it lists uncommitted and untracked paths and commits not
  contained in a fresh fetch of the default branch, the run's branch or the
  run's PR head; if any, it still stops the window but keeps the worktree
  and state files, prints the items and exits 1. `crew kill --discard
  --reason "<why>"` removes anyway after posting the reason on the run's PR
  or issue; `--discard` without `--reason` is refused. `crew down` keeps the
  session and names the windows holding unlanded work. Tests with a temp git
  repo and a bare remote in `scripts/test-crew.py`; `docs/runtimes/tmux.md`
  kill section updated. (issue #172, PR #221, 2026-10-30) Box skill copy:
  none.
- Crew-flow diagram: builder engine order and escalation arrow. (#12, 2026-10-20) Box
  skill copy: no box skill change.
- A failed validation pass never becomes an APPROVE: protocol (stage 7 and merge
  gate) and templates now say so; AC4 consumers and a stale live claim corrected.
  (#25, 2026-10-20) Box skill copy: the gate rule and the AC4 exception are both in
  the box skill; the repo mirrors them.

## Bootstrap (2026-10-19)

### Added

- Framework spec (`docs/specs/framework.md`), README and CI (markdownlint and an
  offline link check). Direct commit to main (no PR). Box skill copy: no box skill change.
