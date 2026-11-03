---
type: added
issue: 673
pr: 705
date: 2026-11-03
box-skill: deferred (tmux mirror deferral; Grok Bot runs express items in the crew lane)
---

Add the express gate to the tmux synthesizer. Its brief takes, for a `crew:express` change whose `class-flavor --express` lane is express, the latest builder `pass=selfgate verdict=pass` at head (checked with `crew-precheck.py --pass selfgate`) in place of the formal approval, needs owner merge-ok at head for `crew:sensitive` or `crew:spec`, and lists `Express self-gate at head` in gate-status. `crew train` applies it per member: `build` carries an express member by its selfgate record's `base` and `sha` (verdict portability), `check` reports the selfgate result and an `express` gate (tightening class or `crew:spec` blocks), `land` stops on a missing or stale selfgate record, and the merge record names `pass=selfgate`. Crew-lane members in the same train are unchanged.
