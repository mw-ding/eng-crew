# Docs index

This is the index for the engineering-bot crew framework docs. Start with the
architecture overview, then read the protocol and the role details.

The framework is generic. Per-repo values appear as placeholders such as
`<owner>`, `<repo>`, `<author-login>` and `<reviewer-login>`. No secrets or
tokens are stored in this repo.

## Find your path

Navigation only: these links point at the docs that own each rule and add no
rule of their own. A role's rendered brief stays its operating instruction.

By role:

- **Owner:** [../README.md](../README.md) for the product and install front
  page, then [flavors.md](flavors.md) for rigor and
  [protocol.md](protocol.md) for steering and the decisions it asks of you.
- **Adopter:** [runbook-new-repo.md](runbook-new-repo.md) by chosen runtime,
  then [bootstrap.md](bootstrap.md), [profile.md](profile.md),
  [release.md](release.md) and the runtime binding
  ([runtimes/tmux.md](runtimes/tmux.md) or
  [runtimes/grok-bot.md](runtimes/grok-bot.md)).
- **Pack author:** [concepts.md](concepts.md), then
  [interfaces.md](interfaces.md) and [runtimes/README.md](runtimes/README.md),
  then [profile.md](profile.md) and [roles-registry.md](roles-registry.md),
  then [packs.md](packs.md) and the selected binding.
- **Coordinator:** [protocol.md](protocol.md), the coordinator sections of
  [roles.md](roles.md), the runtime binding, [scheduling.md](scheduling.md)
  and [self-improve.md](self-improve.md).
- **Builder:** [../AGENTS.md](../AGENTS.md), the worker brief and PR
  templates in [roles.md](roles.md), [verification.md](verification.md) and
  [../templates/evidence/](../templates/evidence/README.md); add
  [express-lane.md](express-lane.md) for an express change.
- **Reviewer-validator:** [../AGENTS.md](../AGENTS.md), the review sections of
  [protocol.md](protocol.md), [roles.md](roles.md) and
  [verification.md](verification.md).
- **Synthesizer:** the stage 7 merge gate in [protocol.md](protocol.md), the
  runtime binding's land procedure and [release.md](release.md) for cuts.
- **Researcher:** the Researcher section of [roles.md](roles.md) and the
  docs the request names.

By task:

- **Change the framework:** [../CONTRIBUTING.md](../CONTRIBUTING.md),
  [../AGENTS.md](../AGENTS.md) and [../scripts/](../scripts/README.md).
- **Understand the flow:** [architecture.md](architecture.md), then
  [concepts.md](concepts.md); diagram sources are in
  [diagrams/](diagrams/README.md).
- **Look up history:** [lessons/README.md](lessons/README.md),
  [findings/README.md](findings/README.md),
  [../CHANGELOG.md](../CHANGELOG.md) and the specs under [specs/](specs/portable.md).
- **Read metrics:** [metrics/README.md](metrics/README.md) and
  [metrics/decisions.md](metrics/decisions.md).

## Available now

Audience: O owner, A adopter, P pack author, C coordinator, B builder, V
reviewer-validator, S synthesizer, R researcher; `all` means every one. Kind:
`rule` (normative: stages, gates, contracts), `reference` (schemas,
inventories, runbooks, overviews), `design` (proposal or build plan, possibly
partly built) or `history` (dated record, not a current rule). A doc with two
kinds mixes them; lifecycle status stays in each doc.

<!-- Keep the rows sorted by the first cell, one row per doc (check-repo.py checks both); a new doc's row goes at its sorted place, not at the end. -->

| Doc | Purpose | Audience | Kind | Contents |
|---|---|---|---|---|
| [../AGENTS.md](../AGENTS.md) | Agent build and review posture | B, V, R | rule | Thin agent guide: doc map, build posture, review posture (what blocks, what is a yellow follow-up) |
| [../CHANGELOG.md](../CHANGELOG.md) | Released change history | all | history | Record of every change |
| [../CONTRIBUTING.md](../CONTRIBUTING.md) | How to change the framework | B, V, C, S | rule | Process for iterating on the framework |
| [../examples/agentconnect/](../examples/agentconnect/README.md) | Worked pilot example | A, P | reference, history | Sanitized worked example (the agentconnect pilot) |
| [../scripts/](../scripts/README.md) | Guard and tooling guide | B, V, C | reference | Secret and token scan, required-docs check, relative link check, guard tests; runs in CI as `repo-guard` |
| [../templates/](../templates/README.md) | Template catalog | A, C, P | reference | Routine and listener templates per role with trigger JSON, `wiring.md` template, reviewer-engine and V2 templates |
| [architecture.md](architecture.md) | Explanatory overview | all | reference | Roles, identities, stages diagram, label reference, marker reference |
| [backends/github.md](backends/github.md) | GitHub backend mapping | C, B, V, S, P, A | rule | GitHub backend: reviews, markers and identities (review types and the events they fire, identity selection, land and merge-up) (13.3, #115); tracking (labels, milestones and board, linkage, steering limits) (13.4, #116); interface mapping: a `gh` command or API call per operation (13.9, #121) |
| [bootstrap.md](bootstrap.md) | Install, pin and preflight | A, C, P | reference, design | Bootstrap (design): `crew bootstrap` entry point, release-bundle pin and record, config resolution, per-runtime install targets with contract gaps, `crew doctor` preflight with fix hints, repo-side setup, self-test, upgrade and uninstall, secrets, build issues (17.1, #144) |
| [concepts.md](concepts.md) | Vocabulary | all | reference | Glossary of abstract protocol terms (change, verdict, state tag, marker, ...) mapped to today's GitHub and Grok Bot terms (13.1, #113) |
| [deliverables.md](deliverables.md) | Deliverable inventory and versioning | A, P, C | reference, design | Deliverables (design): inventory of every path as deliverable or internal, packaging as one bundle per release, SemVer breaking rules, compatibility promise to packs and installs, first versions (R1.1, #145) |
| [express-lane.md](express-lane.md) | Express lane | O, C, B, V, S | rule, design | Express lane (design): opt-in `express` flavor where one builder builds, self-reviews and tests, and the change lands on green CI; scoped F4/I1 (and, under `same`, I2) exceptions, sensitive/spec exclusions, the `selfgate_engine` flip, self-gate loop with the reviewer rubric, `pass=selfgate` record, §7 express gate row, routing, trade-offs, per-lane metric columns, build issues (M18.2, #636) |
| [flavors.md](flavors.md) | Rigor knobs and presets | O, C, B, V, S, P, A | rule, design | Crew flavors (design): rigor knobs, presets `thorough` / `standard` / `fast` / `solo`, the floor no flavor crosses, profile schema proposal and floor validator rules, project / item / change resolution with the path-based class rule, mapping of existing one-off knobs, metrics feedback loop with thresholds, suggestion issue and owner accept path, build issues (18.1, #156) |
| [handoff.md](handoff.md) | Runtime ownership handoff | O, C, P, A | rule, design | Runtime handoff (design): one owning runtime per repo recorded on a control item, read-only fallback, drain or stop, the handoff manifest with its template, resume and reconcile, prompt stop, return path, session rules as config, runtime guards, the C9 contract capability, build issues (21.1, #157) |
| [interfaces.md](interfaces.md) | Backend operation contract | P, C, A | rule | Backend interfaces: minimum operations per concern (change, review, tracker, state tags, markers, CI, events, owner channel), the invariant each protects, capability declaration, single-identity analysis (13.9, #121) |
| [lessons/README.md](lessons/README.md) | Lessons sub-index | C, R | history | Lessons log: entry format and index; first entry is [2026-10-19-bottlenecks.md](lessons/2026-10-19-bottlenecks.md) |
| [merge-enforcement.md](merge-enforcement.md) | Platform merge protection target | O, C, S, A | design | M4 target merge rules, current plan blocker, application recipe, verification, rollback and fail-open |
| [metrics/README.md](metrics/README.md) | Metric field reference | O, C, R | reference | Cycle-time and rounds metrics artifact: field definitions, refresh command, committed `prs.md` / `prs.csv` |
| [metrics/decisions.md](metrics/decisions.md) | Metrics sensors and thresholds | O, C, B, R | rule | Metrics to decisions: sensors, windows, thresholds, rollup vs per-repo, the `metrics-gate` issue and what blocking `M*` feature work means, waiver and lift |
| [metrics/owner-sla-drill.md](metrics/owner-sla-drill.md) | Owner-SLA drill | C, R | design, history | Owner-SLA drill plan (P7): synthetic hold, expected timestamps, pass/fail checks, results table |
| [observe.md](observe.md) | Step summaries | C, B, V, R | rule | Step-summary observe protocol: step lines, `.crew/runs/` paths, promote onto the PR, what reviewers skim, risks |
| [packs.md](packs.md) | Pack contract | P, A, C | rule | Packs: layout (`manifest.toml`, `profile.toml`, binding docs, render overrides), `eng_crew_version` pin and compatibility rule, capability folding, wiring by `--org-profile`, direction rule, denylist check (13.15, #127) |
| [profile.md](profile.md) | Profile schema and defaults | O, C, P, A | reference | `crew.toml` profile schema: every key, type, default and the placeholder it replaces; validated by `scripts/crew-config.py validate` (13.10, #122) |
| [protocol.md](protocol.md) | Stages, markers and gates | C, B, V, S, R, P | rule | Stage protocol: evidence, rounds, duties on wake, merge gate, safety, `/crew` steering |
| [release.md](release.md) | Release cut and publish | O, C, S, A, P | rule, design | Release workflow (design): cut-PR merge trigger, head-bound owner approval, validate and build, tag and GitHub Release, release gate, rollback, update path, session-tooling upstreaming (R1.1, #145) |
| [roles-registry.md](roles-registry.md) | Role registry schema | P, C, A | reference, design | Role registry schema (design): closed keys, all four current roles, validation and migration inventory (15.7, #317) |
| [roles.md](roles.md) | Role, engine and PR contracts | C, B, V, S, R | rule | Worker roles, tiers, engines and quota routing, worktree rules, worker brief and PR templates, coordinator owner-communication rules |
| [runbook-new-repo.md](runbook-new-repo.md) | Onboarding runbook | A, C, P, O | reference, history | Onboarding runbook for a new repo: install by profile (`crew.toml`, validate, resolve, render), prerequisites, labels, collaborators, Project, CI and protection, product-safety checks, listener wiring, first test issue, verification checklist, rollback |
| [runtimes/README.md](runtimes/README.md) | Runtime contract (C1–C9) | P, A, C | rule | Runtime contract: the eight capabilities every runtime provides, the guarantee each protects, gap-declaration format (13.8, #120) |
| [runtimes/grok-bot.md](runtimes/grok-bot.md) | Grok Bot binding | C, B, V, S, A, P | rule | Grok Bot runtime binding: wake wiring, per-PR watches, verified B2 hand-off, comment-listener wakes, lighter-lane routing, routine limits, pilot notes (13.2, #114) |
| [runtimes/harness-adapters.md](runtimes/harness-adapters.md) | Harness adapter contract | P, A, C | rule | Harness adapter interface: launch line, trust and first-run dialogs, turn-end and wake recipe, idle detection, expected foreground process, each tied to C1, C3 or C5; Claude Code and Codex filled in (15.4, #177) |
| [runtimes/multi-device.md](runtimes/multi-device.md) | Multi-host runner | O, C, B, V, P, A | rule, design | Multi-device tmux crew (design): role runs placed on hosts of a private overlay network under one primary; overlay assumptions, host inventory profile keys, placement function, host readiness, hardened remote call and runner, C1–C8 across hosts, failure and partition, security model, forge-less runner hosts with an add-a-runner-host runbook (20.12), build issues (20.1, #158) |
| [runtimes/session-backends.md](runtimes/session-backends.md) | Session backend contract | P, A, C | rule | Session backend interface: create in the background, attach (read-only default), doorbell, identity probe (handle plus start time, C5), state read and kill, each tied to a contract capability; tmux filled in (15.5, #178) |
| [runtimes/session.md](runtimes/session.md) | Session binding | C, B, V, S, R, P, A | rule, design | Session runtime binding (design): proposed `session` selector, coordinator and worker lifecycle, adapters, C1–C9 gaps, attended operation and implementation boundary (17.13, #340) |
| [runtimes/tmux.md](runtimes/tmux.md) | tmux binding | all | rule | tmux runtime binding (shipped in M14 and M14.1): answers to #110 Q1, Q2, Q3, Q5, Q6, Q7 with alternatives, contract table, window layout and naming, spawn and kill mechanics, firstmate design credit (14.1, #130) |
| [scheduling.md](scheduling.md) | Crew scheduler | O, C, B, V, R | rule | Crew scheduler (built): one crew-wide `crew schedule decide` for both leads; observable inputs (demand, priority, worker state, machine load, memory, suites, gateway errors, presence); finish-before-start classes, hysteresis target with ramp limit, pool floors against starvation, overlap trains; decision log and one summary line; what it subsumes; build issues (M18.1, #587) |
| [self-improve.md](self-improve.md) | Self-improve intake | C, B, V, S, R | rule, design | Self-improve intake: triggers, candidate card, accept/close, lesson path, `repo:` vs `crew:` scope, risks |
| [specs/framework.md](specs/framework.md) | Framework spec | O, C, R, P | reference, history | Spec for this repo: goal, requirements R1–R8, layout, source material, slices |
| [specs/portable.md](specs/portable.md) | Portable spec | O, C, R, P, A | reference, history | Spec for portable eng-crew (#110): runtime and tool abstraction, config layers, invariants, target layout, M13/M14 slices, decisions, open questions |
| [triage.md](triage.md) | Always-on triage | O, C, R | design | Always-on triage (design): a recurring sweep by a fresh researcher session on the watcher's timer, a zero-model scan in `crew poll` with P0 detection, learning lookup over duplicates, lessons, findings and owner decisions with citations, rules first and fail closed, auto-apply / propose / never autonomy, P0–P3 bands, `pass=triage` records, a daily log issue and owner replies on the item, shadow mode with an 8-of-10 precision bar, feedback metrics, build issues (M24, #659) |
| [verification.md](verification.md) | Typed runtime evidence | B, V, S, C | rule | Verification protocol: typed runtime evidence per shape (web, CLI, service, API, mobile), role duties, N/A rules, fail-open |

## Planned

Nothing is planned right now. Every doc in the spec's slices has landed and is
listed under Available now.
