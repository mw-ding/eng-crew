---
type: changed
issue: 715
pr: 730
date: 2026-11-03
box-skill: none
---

M20 is re-scoped runner first: the multi-device design gains forge-less hosts (`forge = false`) that take remote test runner jobs only, with the primary as the forge gateway seeding the host mirror over the hardened call, a closed forge-free command set, results by reference, a local fallback that never blocks a gate, and the security model. The spec moves M20 after M21, files the runner build issues (20.13–20.16) and moves the remote role session issues to a follow-up milestone.
