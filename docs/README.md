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
| [architecture.md](architecture.md) | Roles, identities, stages diagram, label reference, marker reference |
| [protocol.md](protocol.md) | Stage protocol: evidence, rounds, duties on wake, merge gate, safety, `/crew` steering |
| [merge-enforcement.md](merge-enforcement.md) | M4 target merge rules, current plan blocker, application recipe, verification, rollback and fail-open |
| [verification.md](verification.md) | Verification protocol: typed runtime evidence per shape (web, CLI, service, API, mobile), role duties, N/A rules, fail-open |
| [observe.md](observe.md) | Step-summary observe protocol: step lines, `.crew/runs/` paths, promote onto the PR, what reviewers skim, risks |
| [self-improve.md](self-improve.md) | Self-improve intake: triggers, candidate card, accept/close, lesson path, `repo:` vs `crew:` scope, risks |
| [roles.md](roles.md) | Worker roles, tiers, engines and quota routing, worktree rules, worker brief and PR templates |
| [../templates/](../templates/README.md) | Routine and listener templates per role with trigger JSON, `wiring.md` template, reviewer-engine and V2 templates |
| [metrics/README.md](metrics/README.md) | Cycle-time and rounds metrics artifact: field definitions, refresh command, committed `prs.md` / `prs.csv` |
| [../scripts/](../scripts/README.md) | Secret and token scan, required-docs check, relative link check, guard tests; runs in CI as `repo-guard` |
| [../examples/agentconnect/](../examples/agentconnect/README.md) | Sanitized worked example (the agentconnect pilot) |
| [lessons/README.md](lessons/README.md) | Lessons log: entry format and index; first entry is [2026-10-19-bottlenecks.md](lessons/2026-10-19-bottlenecks.md) |
| [../CHANGELOG.md](../CHANGELOG.md) | Record of every change |
| [../CONTRIBUTING.md](../CONTRIBUTING.md) | Process for iterating on the framework |
| [runbook-new-repo.md](runbook-new-repo.md) | Onboarding runbook for a new repo: prerequisites, labels, collaborators, Project, CI and protection, product-safety checks, listener wiring, first test issue, verification checklist, rollback |
| [metrics/decisions.md](metrics/decisions.md) | Metrics to decisions: sensors, windows, thresholds, rollup vs per-repo, the `metrics-gate` issue and what blocking `M*` feature work means, waiver and lift |
| [metrics/owner-sla-drill.md](metrics/owner-sla-drill.md) | Owner-SLA drill plan (P7): synthetic hold, expected timestamps, pass/fail checks, results table |

## Planned

Nothing is planned right now. Every doc in the spec's slices has landed and is
listed under Available now.
