---
name: merge-train
description: Synthesizer merge-train procedure (build, land and red-train handling).
---

# Merge train

Trigger: two or more ready PRs under the land rules.

Merge trains are tmux-only: every `mdstack train` action refuses a session
profile, so the session synthesizer lands each ready PR alone (#1041). The
whole procedure, pre-check, build, land and red handling, lives in the
[tmux synthesizer template](../../../../runtimes/tmux/synthesizer.md); no
fragment carries it.
