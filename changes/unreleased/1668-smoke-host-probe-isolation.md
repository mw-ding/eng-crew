---
type: fixed
issue: 1668
pr: TBD
date: 2026-11-12
box-skill: none
---

The bootstrap smoke tests no longer depend on the host's session sandbox: their fixture pins `CREW_SANDBOX_ENV` in the environment the copied bundle's subprocess inherits, so a host that denies writes in the checkout's `.git` reaches the smoke assertion instead of stopping at doctor's sandbox row. A new test denies that probe and shows both smoke outcomes still run, and that the unpinned host does stop there. Doctor's own sandbox tests keep the real probe.
