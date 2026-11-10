---
name: synthesizer
description: Synthesizer role policy shared by every runtime's synthesizer brief (flavor gate, landing authority, land and merge-train procedures).
---

# Synthesizer

Role policy for the synthesizer ([roles](../../../docs/roles.md)), authored
once. Runtime templates include the fragments with a whole-line include
([fragments](../README.md)); nothing here renders on its own.

Role-wide rules:

- [flavor-and-authority.md](flavor-and-authority.md): flavor gate, owner
  merge-ok and signing (tmux and session).
- [usage-line.md](../shared/usage-line.md): usage line above the signature
  of every pass-reporting post (tmux and session).
- [landing-steering.md](../shared/landing-steering.md): landing authority
  and steering (tmux and session).
- [flavor.md](../shared/flavor.md) and
  [landing-authority.md](../shared/landing-authority.md): the Grok Bot
  synthesizer's flavor rule and steering input list.

Procedures:

- [land](skills/land/SKILL.md): merge gate, direct land and land rules.
- [merge-train](skills/merge-train/SKILL.md): train build, land and red
  handling (tmux only).

Bindings: [tmux](../../runtimes/tmux/synthesizer.md),
[session](../../runtimes/session/synthesizer.md) and
[Grok Bot](../../runtimes/grok-bot/synthesizer.md). The tmux and session
change-flavor wording is shorter than the Grok Bot one; both stay as
rendered.
