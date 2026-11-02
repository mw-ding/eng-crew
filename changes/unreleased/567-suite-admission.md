---
type: fixed
issue: 567
pr: 573
date: 2026-11-02
box-skill: none
---

Pool leads admit workers while running suites stay below the profile max_suites cap (defaulting to one per four CPUs) and CPU load stays below the CPU count. An empty reviewer pool retains one slot under known load or suite pressure; unavailable observations still defer admission.
