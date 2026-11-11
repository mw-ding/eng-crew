---
type: added
issue: 1614
pr: TBD
date: 2026-11-11
box-skill: none
---

A stack land lab (`dev/tests/scripts/fixtures/stack-land/run.py`) runs the production session synthesizer against a stub stack-land backend. It covers a held member, red per-member CI and a missing approval (each with zero `land-stack` requests), a fully passing stack (exactly one request), an incomplete readback (no merge post) and a lost acknowledgement (read back, not resent). `test-stack-land-lab.py` checks its plumbing in CI with a scripted engine.
