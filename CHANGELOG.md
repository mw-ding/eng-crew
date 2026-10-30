# Changelog

All notable changes to this repo are recorded here, in the style of
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Every PR adds an entry
(spec R5: date, PR number, summary) and says whether the box skill copy was mirrored (spec R4). See
[CONTRIBUTING.md](CONTRIBUTING.md).

## [Unreleased]

### Added

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
