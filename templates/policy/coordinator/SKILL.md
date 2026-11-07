---
name: coordinator
description: Coordinator (team head) role policy shared by every runtime's coordinator brief (signing, landing authority and milestone admission).
---

# Coordinator

Role policy for the coordinator, the team head
([roles](../../../docs/roles.md)), authored once. Runtime templates include
the fragments with a whole-line include ([fragments](../README.md)); nothing
here renders on its own.

Role-wide rules:

- [landing-steering.md](../shared/landing-steering.md): landing authority
  and steering (tmux and session).
- [signing.md](signing.md) and
  [landing-authority.md](../shared/landing-authority.md): the Grok Bot
  routines' signature and steering input list.

Procedures:

- [dispatch](skills/dispatch/SKILL.md): milestone admission.
- [memory-capture](skills/memory-capture/SKILL.md): core memory promotions
  from platform scratch.

Bindings: [tmux](../../runtimes/tmux/coordinator.md),
[session](../../runtimes/session/coordinator.md) and the Grok Bot
routines ([after merge](../../runtimes/grok-bot/coordinator-after-merge.md),
[steering](../../runtimes/grok-bot/coordinator-steering-dispatcher.md),
[stuck PRs](../../runtimes/grok-bot/coordinator-stuck-pr-sweeper.md),
[wiring](../../runtimes/grok-bot/wiring.md)). The tmux and session
signing wording differs from the Grok Bot one and stays in each brief.
