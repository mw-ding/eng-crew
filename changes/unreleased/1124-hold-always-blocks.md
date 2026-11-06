---
type: fixed
issue: 1124
pr: 1163
date: 2026-11-06
box-skill: deferred to #140
---

`crew:hold` now always stops dispatch: `crew route`, the reviewer pool, the scheduler's holds input, the train gate and train merge-ups block a held PR or issue whatever `runtime.options.hold_label_blocks` says, and the tmux and session builder, reviewer and synthesizer briefs drop the condition. The #111 lane-label meaning is retired; `hold_label_blocks` is still accepted but deprecated and ignored. A `new-head` or `fix-at-head` for a head that already carries the newest round's verdict, with no builder fix note or open rereview after it, now opens no new round. Before, a poll `new-head` with `hold_label_blocks = false` started review passes on held PRs #1039 and #1101, the second a round 2 at an unchanged head.
