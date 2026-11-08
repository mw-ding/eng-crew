---
name: merge-train
description: Synthesizer merge-train procedure (build, land and red-train handling).
---

# Merge train

Trigger: two or more ready PRs under the land rules.

- [merge-train-land-start.md](../../merge-train-land-start.md) and
  [merge-train-land.md](../../merge-train-land.md): land steps. Pre-check,
  build and red handling stay in each runtime template: on tmux a builder
  builds, waits and bisects every train; the session synthesizer does it
  itself. The pause and train-route lines that name a wake or run stay there
  too.
