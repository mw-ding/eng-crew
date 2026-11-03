# Docs index

This is the index for the engineering-bot crew framework docs. Start with the
architecture overview, then read the protocol and the role details.

The framework is generic. Per-repo values appear as placeholders such as
`<owner>`, `<repo>`, `<author-login>` and `<reviewer-login>`. No secrets or
tokens are stored in this repo.

## Available now

<!-- Keep the rows sorted by the first cell, one row per doc (check-repo.py checks both); a new doc's row goes at its sorted place, not at the end. -->

| Doc | Contents |
|---|---|
| [../AGENTS.md](../AGENTS.md) | Thin agent guide: doc map, build posture, review posture (what blocks, what is a yellow follow-up) |
| [../CHANGELOG.md](../CHANGELOG.md) | Record of every change |
| [../CONTRIBUTING.md](../CONTRIBUTING.md) | Process for iterating on the framework |
| [../examples/agentconnect/](../examples/agentconnect/README.md) | Sanitized worked example (the agentconnect pilot) |
| [../scripts/](../scripts/README.md) | Secret and token scan, required-docs check, relative link check, guard tests; runs in CI as `repo-guard` |
| [../templates/](../templates/README.md) | Routine and listener templates per role with trigger JSON, `wiring.md` template, reviewer-engine and V2 templates |
| [architecture.md](architecture.md) | Roles, identities, stages diagram, label reference, marker reference |
| [backends/github.md](backends/github.md) | GitHub backend: reviews, markers and identities (review types and the events they fire, identity selection, land and merge-up) (13.3, #115); tracking (labels, milestones and board, linkage, steering limits) (13.4, #116); interface mapping: a `gh` command or API call per operation (13.9, #121) |
| [bootstrap.md](bootstrap.md) | Bootstrap (design): `crew bootstrap` entry point, release-bundle pin and record, config resolution, per-runtime install targets with contract gaps, `crew doctor` preflight with fix hints, repo-side setup, self-test, upgrade and uninstall, secrets, build issues (17.1, #144) |
| [concepts.md](concepts.md) | Glossary of abstract protocol terms (change, verdict, state tag, marker, ...) mapped to today's GitHub and Grok Bot terms (13.1, #113) |
| [deliverables.md](deliverables.md) | Deliverables (design): inventory of every path as deliverable or internal, packaging as one bundle per release, SemVer breaking rules, compatibility promise to packs and installs, first versions (R1.1, #145) |
| [flavors.md](flavors.md) | Crew flavors (design): rigor knobs, presets `thorough` / `standard` / `fast` / `solo`, the floor no flavor crosses, profile schema proposal and floor validator rules, project / item / change resolution with the path-based class rule, mapping of existing one-off knobs, metrics feedback loop with thresholds, suggestion issue and owner accept path, build issues (18.1, #156) |
| [handoff.md](handoff.md) | Runtime handoff (design): one owning runtime per repo recorded on a control item, read-only fallback, drain or stop, the handoff manifest with its template, resume and reconcile, prompt stop, return path, session rules as config, runtime guards, the C9 contract capability, build issues (21.1, #157) |
| [interfaces.md](interfaces.md) | Backend interfaces: minimum operations per concern (change, review, tracker, state tags, markers, CI, events, owner channel), the invariant each protects, capability declaration, single-identity analysis (13.9, #121) |
| [lessons/README.md](lessons/README.md) | Lessons log: entry format and index; first entry is [2026-10-19-bottlenecks.md](lessons/2026-10-19-bottlenecks.md) |
| [merge-enforcement.md](merge-enforcement.md) | M4 target merge rules, current plan blocker, application recipe, verification, rollback and fail-open |
| [metrics/README.md](metrics/README.md) | Cycle-time and rounds metrics artifact: field definitions, refresh command, committed `prs.md` / `prs.csv` |
| [metrics/decisions.md](metrics/decisions.md) | Metrics to decisions: sensors, windows, thresholds, rollup vs per-repo, the `metrics-gate` issue and what blocking `M*` feature work means, waiver and lift |
| [metrics/owner-sla-drill.md](metrics/owner-sla-drill.md) | Owner-SLA drill plan (P7): synthetic hold, expected timestamps, pass/fail checks, results table |
| [observe.md](observe.md) | Step-summary observe protocol: step lines, `.crew/runs/` paths, promote onto the PR, what reviewers skim, risks |
| [packs.md](packs.md) | Packs: layout (`manifest.toml`, `profile.toml`, binding docs, render overrides), `eng_crew_version` pin and compatibility rule, capability folding, wiring by `--org-profile`, direction rule, denylist check (13.15, #127) |
| [profile.md](profile.md) | `crew.toml` profile schema: every key, type, default and the placeholder it replaces; validated by `scripts/crew-config.py validate` (13.10, #122) |
| [protocol.md](protocol.md) | Stage protocol: evidence, rounds, duties on wake, merge gate, safety, `/crew` steering |
| [release.md](release.md) | Release workflow (design): cut-PR merge trigger, head-bound owner approval, validate and build, tag and GitHub Release, release gate, rollback, update path, session-tooling upstreaming (R1.1, #145) |
| [roles-registry.md](roles-registry.md) | Role registry schema (design): closed keys, all four current roles, validation and migration inventory (15.7, #317) |
| [roles.md](roles.md) | Worker roles, tiers, engines and quota routing, worktree rules, worker brief and PR templates, coordinator owner-communication rules |
| [runbook-new-repo.md](runbook-new-repo.md) | Onboarding runbook for a new repo: install by profile (`crew.toml`, validate, resolve, render), prerequisites, labels, collaborators, Project, CI and protection, product-safety checks, listener wiring, first test issue, verification checklist, rollback |
| [runtimes/README.md](runtimes/README.md) | Runtime contract: the eight capabilities every runtime provides, the guarantee each protects, gap-declaration format (13.8, #120) |
| [runtimes/grok-bot.md](runtimes/grok-bot.md) | Grok Bot runtime binding: wake wiring, per-PR watches, verified B2 hand-off, comment-listener wakes, lighter-lane routing, routine limits, pilot notes (13.2, #114) |
| [runtimes/harness-adapters.md](runtimes/harness-adapters.md) | Harness adapter interface: launch line, trust and first-run dialogs, turn-end and wake recipe, idle detection, expected foreground process, each tied to C1, C3 or C5; Claude Code and Codex filled in (15.4, #177) |
| [runtimes/multi-device.md](runtimes/multi-device.md) | Multi-device tmux crew (design): role runs placed on hosts of a private overlay network under one primary; overlay assumptions, host inventory profile keys, placement function, host readiness, hardened remote call and runner, C1–C8 across hosts, failure and partition, security model, build issues (20.1, #158) |
| [runtimes/session-backends.md](runtimes/session-backends.md) | Session backend interface: create in the background, attach (read-only default), doorbell, identity probe (handle plus start time, C5), state read and kill, each tied to a contract capability; tmux filled in (15.5, #178) |
| [runtimes/session.md](runtimes/session.md) | Session runtime binding (design): proposed `session` selector, coordinator and worker lifecycle, adapters, C1–C9 gaps, attended operation and implementation boundary (17.13, #340) |
| [runtimes/tmux.md](runtimes/tmux.md) | tmux runtime binding (shipped in M14 and M14.1): answers to #110 Q1, Q2, Q3, Q5, Q6, Q7 with alternatives, contract table, window layout and naming, spawn and kill mechanics, firstmate design credit (14.1, #130) |
| [scheduling.md](scheduling.md) | Crew scheduler (design): one crew-wide `crew schedule decide` for both leads; observable inputs (demand, priority, worker state, machine load, memory, suites, gateway errors, presence); finish-before-start classes, hysteresis target with ramp limit, pool floors against starvation, overlap-aware dispatch and trains; decision log and one summary line; what it subsumes; build issues (M18.1, #587) |
| [self-improve.md](self-improve.md) | Self-improve intake: triggers, candidate card, accept/close, lesson path, `repo:` vs `crew:` scope, risks |
| [specs/framework.md](specs/framework.md) | Spec for this repo: goal, requirements R1–R8, layout, source material, slices |
| [specs/portable.md](specs/portable.md) | Spec for portable eng-crew (#110): runtime and tool abstraction, config layers, invariants, target layout, M13/M14 slices, decisions, open questions |
| [verification.md](verification.md) | Verification protocol: typed runtime evidence per shape (web, CLI, service, API, mobile), role duties, N/A rules, fail-open |

## Planned

Nothing is planned right now. Every doc in the spec's slices has landed and is
listed under Available now.
