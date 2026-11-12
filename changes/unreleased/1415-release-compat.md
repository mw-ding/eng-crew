---
type: added
issue: 1415
pr: 1705
date: 2026-11-11
box-skill: none
---

Release validation now refuses a minor or patch cut that breaks a pack manifest the published predecessor accepted. `scripts/release-compat.py`, run by `release.yml` `validate`, pins the greatest stable tag below the cut version. It checks a named corpus from that tree, the shipped GitHub manifest and an external pack derived from it, with the baseline's validator and then the candidate's. A newly failing manifest names the baseline, the manifest, the failing requirement and the major to cut. A major cut allows the break; an unreadable baseline fails with a repair step.
