---
type: changed
issue: 778
pr: 808
date: 2026-11-03
box-skill: deferred to #140 (coordinator posts the per-PR mirror deferral record)
---

The Grok Bot B1, B2 and V2 prompts now build every build, fix, review and validate worker turn's run block with `crew brief` (Item, Pass, Base at the live head, Round, Claim, Engine and Worktree) and append its `## This run` block verbatim to the worker prompt, refusing to dispatch when `crew brief` exits 2. V2 states that review and validation each run in a fresh, independent session that reuses neither the builder's conversation nor the other pass's session, and that validation never sees the review output. `scripts/test-render-parity.py` renders the real templates and parses each recipe through `crew brief` to prove the fields reach the worker.
