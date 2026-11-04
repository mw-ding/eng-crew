---
type: added
issue: 785
pr: 816
date: 2026-11-04
box-skill: none (internal campaign script and doc; no template or box-skill changes)
---

`scripts/campaign-sandbox.py` sets up the M25 level-a disposable sandbox (25.03): a bare origin and seeded clone with a local CI fixture, an isolated sandbox profile (own repo slug, tmux session and roots), a control item with labels and fixture identities, and the guarded run manifest, refusing a non-empty or production-overlapping root before any write. `teardown` kills only the sandbox session, records retained work and the sentinel check, and removes the sandbox only when nothing is retained. `plan-forge` prints the level-b forge setup without running it; level b is blocked on owner account access. `docs/campaign-harness.md` gains the level a/b/c runbook.
