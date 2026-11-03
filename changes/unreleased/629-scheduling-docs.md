---
type: removed
issue: 629
pr: 709
date: 2026-11-03
box-skill: none
---

Retire `crew lead capacity` and its `--suites`/`--queued` flags: both leads now admit through `crew schedule decide`, and no brief calls it. `docs/scheduling.md` is marked built and records the owner's 2026-11-03 overlap decision (D + S9): builds are not overlap-sequenced, S8 (#626) is closed unbuilt and the `Touches:` triage footprint is dropped, while overlap trains (#627) stay. The tmux binding's Q6, builder lead section and Scaling policy inputs point to the scheduler as built.
