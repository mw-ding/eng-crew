# Docs index

This is the index for the engineering-bot crew framework docs. Start with the
architecture overview, then read the protocol and the role details.

The framework is generic. Per-repo values appear as placeholders such as
`<owner>`, `<repo>`, `<author-login>` and `<reviewer-login>`. No secrets or
tokens are stored in this repo.

## Available now

| Doc | Contents |
|---|---|
| [specs/framework.md](specs/framework.md) | Spec for this repo: goal, requirements R1–R8, layout, source material, slices |
| [specs/portable.md](specs/portable.md) | Spec for portable eng-crew (#110): runtime and tool abstraction, config layers, invariants, target layout, M13/M14 slices, decisions, open questions |
| [concepts.md](concepts.md) | Glossary of abstract protocol terms (change, verdict, state tag, marker, ...) mapped to today's GitHub and Grok Bot terms (13.1, #113) |
| [runtimes/README.md](runtimes/README.md) | Runtime contract: the eight capabilities every runtime provides, the guarantee each protects, gap-declaration format (13.8, #120) |
| [runtimes/harness-adapters.md](runtimes/harness-adapters.md) | Harness adapter interface: launch line, trust and first-run dialogs, turn-end and wake recipe, idle detection, expected foreground process, each tied to C1, C3 or C5; Claude Code and Codex filled in (15.4, #177) |
| [runtimes/grok-bot.md](runtimes/grok-bot.md) | Grok Bot runtime binding: wake wiring, per-PR watches, verified B2 hand-off, comment-listener wakes, lighter-lane routing, routine limits, pilot notes (13.2, #114) |
| [backends/github.md](backends/github.md) | GitHub backend: reviews, markers and identities (review types and the events they fire, identity selection, land and merge-up) (13.3, #115); tracking (labels, milestones and board, linkage, steering limits) (13.4, #116); interface mapping: a `gh` command or API call per operation (13.9, #121) |
| [interfaces.md](interfaces.md) | Backend interfaces: minimum operations per concern (change, review, tracker, state tags, markers, CI, events, owner channel), the invariant each protects, capability declaration, single-identity analysis (13.9, #121) |
| [profile.md](profile.md) | `crew.toml` profile schema: every key, type, default and the placeholder it replaces; validated by `scripts/crew-config.py validate` (13.10, #122) |
| [packs.md](packs.md) | Packs: layout (`manifest.toml`, `profile.toml`, binding docs, render overrides), `eng_crew_version` pin and compatibility rule, capability folding, wiring by `--org-profile`, direction rule, denylist check (13.15, #127) |
| [runtimes/tmux.md](runtimes/tmux.md) | tmux runtime binding (shipped in M14 and M14.1): answers to #110 Q1, Q2, Q3, Q5, Q6, Q7 with alternatives, contract table, window layout and naming, spawn and kill mechanics, firstmate design credit (14.1, #130) |
| [deliverables.md](deliverables.md) | Deliverables (design): inventory of every path as deliverable or internal, packaging as one bundle per release, SemVer breaking rules, compatibility promise to packs and installs, first versions (R1.1, #145) |
| [release.md](release.md) | Release workflow (design): manual dispatch, validate and build, owner approval, tag and GitHub Release, release gate draft, rollback, update path, session-tooling upstreaming (R1.1, #145) |
| [bootstrap.md](bootstrap.md) | Bootstrap (design): `crew bootstrap` entry point, release-bundle pin and record, config resolution, per-runtime install targets with contract gaps, `crew doctor` preflight with fix hints, repo-side setup, self-test, upgrade and uninstall, secrets, build issues (17.1, #144) |
| [backends/github.md](backends/github.md) | GitHub backend: reviews, markers and identities (review types and the events they fire, identity selection, land and merge-up) (13.3, #115) |
| [backends/github.md](backends/github.md) | GitHub backend: reviews, markers and identities (review types and the events they fire, identity selection, land and merge-up) (13.3, #115); tracking (labels, milestones and board, linkage, steering limits) (13.4, #116) |
| [../AGENTS.md](../AGENTS.md) | Thin agent guide: doc map, build posture, review posture (what blocks, what is a yellow follow-up) |
| [architecture.md](architecture.md) | Roles, identities, stages diagram, label reference, marker reference |
| [protocol.md](protocol.md) | Stage protocol: evidence, rounds, duties on wake, merge gate, safety, `/crew` steering |
| [merge-enforcement.md](merge-enforcement.md) | M4 target merge rules, current plan blocker, application recipe, verification, rollback and fail-open |
| [verification.md](verification.md) | Verification protocol: typed runtime evidence per shape (web, CLI, service, API, mobile), role duties, N/A rules, fail-open |
| [observe.md](observe.md) | Step-summary observe protocol: step lines, `.crew/runs/` paths, promote onto the PR, what reviewers skim, risks |
| [self-improve.md](self-improve.md) | Self-improve intake: triggers, candidate card, accept/close, lesson path, `repo:` vs `crew:` scope, risks |
| [roles.md](roles.md) | Worker roles, tiers, engines and quota routing, worktree rules, worker brief and PR templates, coordinator owner-communication rules |
| [../templates/](../templates/README.md) | Routine and listener templates per role with trigger JSON, `wiring.md` template, reviewer-engine and V2 templates |
| [metrics/README.md](metrics/README.md) | Cycle-time and rounds metrics artifact: field definitions, refresh command, committed `prs.md` / `prs.csv` |
| [../scripts/](../scripts/README.md) | Secret and token scan, required-docs check, relative link check, guard tests; runs in CI as `repo-guard` |
| [../examples/agentconnect/](../examples/agentconnect/README.md) | Sanitized worked example (the agentconnect pilot) |
| [lessons/README.md](lessons/README.md) | Lessons log: entry format and index; first entry is [2026-10-19-bottlenecks.md](lessons/2026-10-19-bottlenecks.md) |
| [../CHANGELOG.md](../CHANGELOG.md) | Record of every change |
| [../CONTRIBUTING.md](../CONTRIBUTING.md) | Process for iterating on the framework |
| [runbook-new-repo.md](runbook-new-repo.md) | Onboarding runbook for a new repo: install by profile (`crew.toml`, validate, resolve, render), prerequisites, labels, collaborators, Project, CI and protection, product-safety checks, listener wiring, first test issue, verification checklist, rollback |
| [metrics/decisions.md](metrics/decisions.md) | Metrics to decisions: sensors, windows, thresholds, rollup vs per-repo, the `metrics-gate` issue and what blocking `M*` feature work means, waiver and lift |
| [metrics/owner-sla-drill.md](metrics/owner-sla-drill.md) | Owner-SLA drill plan (P7): synthetic hold, expected timestamps, pass/fail checks, results table |

## Planned

Nothing is planned right now. Every doc in the spec's slices has landed and is
listed under Available now.
