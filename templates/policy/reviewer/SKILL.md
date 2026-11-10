---
name: reviewer
description: Reviewer-validator role policy shared by every runtime's reviewer brief (flavor and validation skip, review passes, delta re-review).
---

# Reviewer

Role policy for the reviewer-validator ([roles](../../../docs/roles.md)),
authored once (#1184 pilot). Runtime templates include the fragments with a
whole-line include ([fragments](../README.md)); nothing here renders on its
own.

Role-wide rules:

- [flavor.md](../shared/flavor.md): flavor line and change-flavor rule.
- [flavor-validation.md](flavor-validation.md) and
  [flavor-validation-end.md](flavor-validation-end.md): the validation
  skip. Who records a skip stays in each runtime template.
- [no-downloads.md](../shared/no-downloads.md): local tools only (tmux and
  session).
- [usage-line.md](../shared/usage-line.md): usage line above the signature
  of every pass-reporting post (tmux and session).

Procedures:

- [review](skills/review/SKILL.md): numbered review and validate passes.
- [rereview](skills/rereview/SKILL.md): delta re-review.

Bindings: [tmux](../../runtimes/tmux/reviewer.md),
[session](../../runtimes/session/reviewer.md) and Grok Bot
[V2](../../runtimes/grok-bot/reviewer-v2-watch.md).
