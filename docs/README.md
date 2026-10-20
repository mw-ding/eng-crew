# Docs index

This is the index for the engineering-bot crew framework docs. Start with the
architecture overview, then read the protocol and the role details.

The framework is generic. Per-repo values appear as placeholders such as
`<owner>`, `<repo>`, `<author-login>` and `<reviewer-login>`. No secrets or
tokens are stored in this repo.

## Available now

| Doc | Contents |
|---|---|
| [specs/framework.md](specs/framework.md) | Spec for this repo: goal, requirements R1–R7, layout, source material, slices |
| [architecture.md](architecture.md) | Roles, identities, stages diagram, label reference, marker reference |
| [protocol.md](protocol.md) | Stage protocol: evidence, rounds, duties on wake, merge gate, safety, `/crew` steering |

## Planned

These docs are not written yet. They are listed as plain text on purpose, so the
link check does not fail on files that do not exist. Each becomes a link when
its slice lands. Slice letters are defined in the spec.

| Doc | Contents | Slice |
|---|---|---|
| `docs/roles.md` | Roles, tiers, engines, quota routing, worktree rules, worker brief template | C |
| `templates/` | Routine and listener prompt templates per role with trigger JSON, `wiring.md` template, reviewer-engine and V2 templates | D |
| `examples/agentconnect/` | Sanitized worked example | D |
| `docs/runbook-new-repo.md` | Onboarding runbook and verification checklist for a new repo | E |
| `docs/lessons/` | Dated lessons log, starting with `2026-10-19-bottlenecks.md` | F |
| `CHANGELOG.md` | Record of every change | F |
| `CONTRIBUTING.md` | Process for iterating on the framework | F |
| `scripts/` | Secret and token scan, required-docs check, link check, wired into CI | G |
