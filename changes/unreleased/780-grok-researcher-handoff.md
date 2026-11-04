---
type: added
issue: 780
pr: 813
date: 2026-11-03
box-skill: deferred to #140
---

Grok Bot gets the researcher (Riley) parent handoff. The new `templates/runtimes/grok-bot/researcher.md` worker brief and the wiring doc's section 2e have the coordinator's parent turn post one signed request on the source issue, then start one fresh read-only worker from the brief plus a `crew brief` run block naming the engine it actually runs. The worker signs with that engine, posts one signed `[Riley/research]` finding with its `pass=research` marker and returns the URL; the parent verifies the URL before relaying the TL;DR. No listener, routine, research gate or tmux command is involved. `docs/roles.md` and `templates/README.md` name the Grok handoff, and `test-render-parity.py` pins the rules. The box-skill mirror of this Grok template change is deferred to #140.
