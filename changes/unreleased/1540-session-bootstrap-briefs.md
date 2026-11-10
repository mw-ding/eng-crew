---
type: fixed
issue: 1540
pr: 1570
date: 2026-11-09
box-skill: none
---

`mdstack bootstrap` on a session profile (`runtime.name = "session"`) no longer fails its `briefs` self-test: the check now looks for the session runtime's own `runtime/<role>.md` briefs instead of the Grok Bot names (`runtime/builder-b1.md` and others) it used for every runtime but tmux. The Grok Bot "Create the routines" human step is printed only for `grok-bot`; a session install prints `Run mdstack up --project <file>`, which starts its coordinator. tmux and grok-bot behaviour is unchanged.
