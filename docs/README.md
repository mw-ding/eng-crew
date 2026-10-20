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
| [roles.md](roles.md) | Worker roles, tiers, engines and quota routing, worktree rules, worker brief and PR templates |
| [../templates/](../templates/README.md) | Routine and listener templates per role with trigger JSON, `wiring.md` template, reviewer-engine and V2 templates |
| [../examples/agentconnect/](../examples/agentconnect/README.md) | Sanitized worked example (the agentconnect pilot) |
| [runbook-new-repo.md](runbook-new-repo.md) | Onboarding runbook for a new repo: prerequisites, labels, collaborators, Project, CI and protection, product-safety checks, listener wiring, first test issue, verification checklist, rollback |

## Planned

These docs are not written yet. They are listed as plain text on purpose, so the
link check does not fail on files that do not exist. Each becomes a link when
its slice lands. Slice letters are defined in the spec.

| Doc | Contents | Slice |
|---|---|---|
| `docs/lessons/` | Dated lessons log, starting with `2026-10-19-bottlenecks.md` | F |
| `CHANGELOG.md` | Record of every change | F |
| `CONTRIBUTING.md` | Process for iterating on the framework | F |
| `scripts/` | Secret and token scan, required-docs check, link check, wired into CI | G |
