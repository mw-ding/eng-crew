---
type: fixed
issue: 1082
pr: 1651
date: 2026-11-10
box-skill: none
---

`mdstack up` on a tmux crew whose session already runs now ensures the enabled leads and lifecycle floors instead of returning at "already running", so an incoming runtime that ran `mdstack up` before its handoff ack (window 0 only, leads refused while read-only) gets its builder, reviewer and synthesizer leads from the `mdstack up` it runs after the ack and holds. `lead.ensure` keeps its ownership gate and is a no-op for a live lead, so a repeated up starts no duplicate, and `--coordinator-only` and `launch.roles` other than `tmux` are still respected. `docs/handoff.md` resume step 6 and the tmux return path now name that post-ack `mdstack up`.
