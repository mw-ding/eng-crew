---
type: added
issue: 673
pr: 705
date: 2026-11-03
box-skill: deferred (tmux mirror deferral; Grok Bot runs express items in the crew lane)
---

Add the express gate to the tmux synthesizer and `crew train`. `crew train` resolves a `crew:express` change by program: the newest signed coordinator item record on its one linked issue must resolve `express` (`item-flavor.py`, with the issue and PR labels), and no changed path, both rename paths, may match a tightening class (`class-flavor --express`). Only a change resolved express takes the latest builder `pass=selfgate verdict=pass` at head (checked with `crew-precheck.py --pass selfgate`) in place of the formal approval; any other change, labelled or not, needs the crew-lane verdict. `build` carries an express member by its selfgate record's `base` and `sha` and drops an unreadable one (`express-unreadable`); `check` reports the selfgate result and an `express` gate (crew lane, unreadable resolution, or `crew:spec` without merge-ok block); `land` re-resolves at head and stops on a missing or stale record; the merge record names `pass=selfgate`. The synthesizer brief's step 2 names the express approval, with doc pointers shortened to keep the brief inside its size budget headroom.
