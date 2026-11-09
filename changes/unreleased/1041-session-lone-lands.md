---
type: fixed
issue: 1041
pr: 1505
date: 2026-11-09
box-skill: none
---

The session synthesizer brief no longer copies the tmux merge-train recipe: `mdstack train` refuses a session profile, so session lands each ready PR alone, one per run, under a session land rule. The shared merge gate now resolves express with `core/crew-config.py class-flavor --express` instead of `mdstack train check`. `docs/runtimes/session.md` states that merge trains and `land.mode = "async"` are tmux-only, and a render test pins that the session brief runs no `train`, `land` or `land-lock` command.
