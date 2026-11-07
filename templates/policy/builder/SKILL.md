---
name: builder
description: Builder role policy shared by every runtime's builder brief (flavor, signing, local tools, build and fix procedures).
---

# Builder

Role policy for the builder ([roles](../../../docs/roles.md)), authored
once. Runtime templates include the fragments with a whole-line include
([fragments](../README.md)); nothing here renders on its own. Each runtime
template keeps only its mechanics: wake, delivery, worktree, environment and
status lines.

Role-wide rules:

- [flavor.md](../shared/flavor.md): flavor line and change-flavor rule.
- [signing.md](signing.md): signature and attribution.
- [no-downloads.md](../shared/no-downloads.md): local tools only (tmux and
  session).

Procedures:

- [build](skills/build/SKILL.md): build pass and CLI evidence.
- [fix](skills/fix/SKILL.md): fix rounds, express self-gate and PR
  conventions.

Bindings: [tmux](../../runtimes/tmux/builder.md),
[session](../../runtimes/session/builder.md), Grok Bot
[B1](../../runtimes/grok-bot/builder-b1.md) and
[B2](../../runtimes/grok-bot/builder-b2.md). Grok Bot keeps its own
routine prose for intake, local checks and the express fallback (it has no
self-gate or forge-less runner) and includes only the role-wide rules.
