---
name: researcher
description: Researcher role policy (research findings, triage sweeps and docs passes, with each runtime's write authority).
---

# Researcher

Role policy for the researcher ([roles](../../../docs/roles.md)). No
researcher text is shared word for word across runtimes yet, so there is no
fragment here: the tmux brief holds the full policy and the Grok Bot worker
brief a shorter form.

Procedures:

- [research](skills/research/SKILL.md): one finding per request.
- [triage-sweep](skills/triage-sweep/SKILL.md): triage sweep (tmux).
- [docs-pass](skills/docs-pass/SKILL.md): docs pass (tmux).

Bindings: [tmux](../../runtimes/tmux/researcher.md) and
[Grok Bot](../../runtimes/grok-bot/researcher.md). Session has no
researcher. Write authority differs per binding: on tmux a design-doc
deliverable may push a `researcher/` docs branch and open a PR; the Grok
Bot worker never pushes.
