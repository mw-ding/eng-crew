---
name: land
description: Synthesizer land procedure (step 1-2 merge gate, direct-land CI check and gate-status reporting).
---

# Land

Trigger: a PR approved and ready to land.

- [merge-gate.md](../../merge-gate.md): steps 1 and 2.
- [direct-land-ci.md](../../direct-land-ci.md): the direct-land CI check.
- [gate-status.md](../../gate-status.md): verdict portability and
  gate-status reporting.

Each runtime authors step 3 (the land step and lock), its land rules and
its wake or end-the-run lines: the
[tmux](../../../../runtimes/tmux/synthesizer.md) rules choose direct or
train; the [session](../../../../runtimes/session/synthesizer.md) rules land
each ready PR alone (#1041). The merge gate stays in
[the protocol](../../../../../docs/protocol.md) §7.
