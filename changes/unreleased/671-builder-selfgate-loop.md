---
type: added
issue: 671
pr: 704
date: 2026-11-03
box-skill: deferred (tmux mirror deferral; Grok Bot runs express items in the crew lane)
---

Add the express self-gate loop to the tmux builder brief. On an express change (the `express` item record plus `crew:express`, resolved by `class-flavor --express`), the builder writes a self-gate brief in `.crew/`, runs a fresh read-only review sub-session on the `selfgate_engine` mode's engine with the protocol §3 review rubric and the adapter's code-review skill, fixes findings until a pass or `caps[0]`, posts the `pass=selfgate` record and checks it with `crew-precheck.py --pass selfgate`, and falls back to the crew lane on a capped open finding, a new sensitive or tightening match, or the owner's ask. The renderer fills `<flavor-selfgate-engine>` from `flavor.selfgate_engine` (default `different`), and harness adapters gain a code-review skill field (Claude Code `code-review`, Codex `codex review`; none declared for Pi, Cursor and Muse).
