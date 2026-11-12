---
type: added
issue: 1725
pr: TBD
date: 2026-11-12
box-skill: none
---

The coordinator's spec bookends now name the project's configured specs home instead of a fixed `docs/specs/`: `[docs] homes.specs` when set, or the new `[docs] specs_external`, an absolute URL naming a tracker item or document outside the repository (mutually exclusive with `homes.specs`; a reference, never a path or command). With an external home, `mdstack bootstrap` seeds no local spec and `docs-scan.py` records the home under `unchecked` instead of reporting a missing directory. Unset profiles render byte-identically; spec-first, `[spec] paths` and every merge and evidence rule are unchanged.
