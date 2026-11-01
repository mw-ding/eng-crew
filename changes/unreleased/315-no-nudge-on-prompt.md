---
type: fixed
issue: 315
pr: 331
date: 2026-11-01
box-skill: none
---

tmux nudges never type into a prompt (safety fix): `crew watch` typed its
`wake: watcher` line plus `Enter` into an idle window 0, and `crew send`
typed its `inbox: <msg-id>` nudge into a role window, even when the pane
showed a blocking prompt. Claude Code's permission prompt and Codex's
approval prompt preselect yes, so that `Enter` could approve a command
nobody reviewed. Both now check `dialog()` (the prompt and fatal-error
screens of #289) first and press no key when it matches. `crew send` still
appends the inbox line, prints `dialog: a prompt is on its screen; nothing
typed` with `treat <window> as ambiguous` and exits 4; it also re-checks
before each `Enter` retry. The watcher queues a `dialog` wake for window 0
(liveness `ambiguous`, action `escalate`) instead of the wake line. A
normal screen still gets the nudge.
