---
name: researcher
description: Researcher role policy (research findings, triage sweeps, docs passes and reflection reports, with each runtime's write authority).
---

# Researcher

Role policy for the researcher ([roles](../../../docs/roles.md)). No
researcher text is shared word for word across runtimes yet, so there is no
fragment here: the tmux brief holds the full policy and the Grok Bot worker
brief a shorter form.

Role-wide rules:

- [usage-line.md](../shared/usage-line.md): usage line above the signature
  of every report post (tmux).

Procedures:

- [research](skills/research/SKILL.md): one finding per request.
- [triage-sweep](skills/triage-sweep/SKILL.md): triage sweep (tmux).
- [docs-pass](skills/docs-pass/SKILL.md): docs pass (tmux).
- [protocol-reflection](skills/protocol-reflection/SKILL.md): reflection
  report (tmux). Its steps live in the skill file; the brief points to it.

Bindings: [tmux](../../runtimes/tmux/researcher.md) and
[Grok Bot](../../runtimes/grok-bot/researcher.md). Session has no
researcher. Write authority differs per binding: on tmux a design-doc
deliverable may push a `researcher/` docs branch and open a PR; the Grok
Bot worker never pushes.
