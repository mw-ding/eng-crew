---
type: added
issue: 1605
pr: TBD
date: 2026-11-10
box-skill: none
---

Session stack land (M42 B4). A change backend may declare `land.stack = true` with the conditional `change.land-stack` and `change.stack-status` operations, and `land.stack_tests_against_tip` for a combined-stack test on the current tip; `resolve` checks both. The session synthesizer brief then renders a stack-land recipe: every §7 gate is checked for every member at its own head, one failing member refuses the whole stack, and otherwise `mdstack land stack --stack <n>:<head-sha>,...` records one intent, re-reads every member head and sends one atomic request only when every member reads `none`. A lost acknowledgement is read back, never resent. Only a complete per-member readback succeeds, printing one merge record and marker per member with its landed revision and, when declared, the named combined-stack check; a missing, reordered, malformed or split readback is unknown and records nothing. `mdstack land resume` reads stack intents back without requesting and `mdstack land stack-done` clears a landed one. Without the binding, session lands stay one per run; tmux renders and trains are unchanged.
