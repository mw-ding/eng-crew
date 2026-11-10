---
type: changed
issue: 1033
pr: 1574
date: 2026-11-09
box-skill: none
---

`scripts/changelog-cut.py` now ships in the release bundle as a Deliverable, so a pack on a host with only the installed bundle can run the `release.cut` binding without a clone of mdstack. `docs/release.md` names the bundled command, and `test-release-bundle.py` cuts a scratch pack's changelog with the script taken from a freshly built bundle.
