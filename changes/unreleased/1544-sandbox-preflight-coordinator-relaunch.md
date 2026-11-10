---
type: fixed
issue: 1544
pr: 1580
date: 2026-11-10
box-skill: none
---

`mdstack doctor` gains a tmux `sandbox` row, and `mdstack up` (and `mdstack up <role>`) refuse before starting any window, when a launcher sandboxes sessions with no writable root over the checkout's `.git` and neither `runtime.options.sandbox_env` nor `CREW_SANDBOX_ENV` is set: a create-and-remove probe in that `.git` is denied, or a used engine's harness adapter declares `sandbox_roots(values)` that do not cover it. The one-line fix names `runtime.options.sandbox_env`. `mdstack restart <coordinator-window> [--resume <id>]` relaunches the live coordinator in place with the current `sandbox_env` and `CREW_*` environment, resuming its conversation, and refuses while the land lock is held or when run from window 0 itself.
