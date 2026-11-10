---
type: fixed
issue: 1539
pr: TBD
date: 2026-11-09
box-skill: none
---

The session synthesizer brief carries gate-status reporting and the verdict-portability line again. Both were dropped when #1041 inlined the land rules, while the shared merge gate still pointed "below" to them. They now live in one fragment, `templates/policy/synthesizer/gate-status.md`, that the tmux and session briefs both include. The tmux render is unchanged, and a render test pins the session brief.
