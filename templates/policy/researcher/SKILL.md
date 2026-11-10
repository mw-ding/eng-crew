---
name: researcher
description: Researcher role policy (research findings, triage sweeps, docs passes and reflection reports, with each runtime's write authority).
---

# Researcher

Role policy for the researcher ([roles](../../../docs/roles.md)). One
fragment: [triage-sweep.md](triage-sweep.md), the Triage sweep policy. The
tmux brief holds the rest of the policy and the Grok Bot worker brief a
shorter form.

Procedures:

- [research](skills/research/SKILL.md): one finding per request.
- [triage-sweep](skills/triage-sweep/SKILL.md): triage sweep (tmux, session).
- [docs-pass](skills/docs-pass/SKILL.md): docs pass (tmux).
- [protocol-reflection](skills/protocol-reflection/SKILL.md): reflection
  report (tmux). Its steps live in the skill file; the brief points to it.

Bindings: [tmux](../../runtimes/tmux/researcher.md),
[Grok Bot](../../runtimes/grok-bot/researcher.md) and the sweep-only
[session](../../runtimes/session/researcher.md) brief. Write authority
differs per binding: on tmux a design-doc
deliverable may push a `researcher/` docs branch and open a PR; the Grok
Bot worker never pushes.
