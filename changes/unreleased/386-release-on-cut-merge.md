---
type: changed
issue: 386
pr: TBD
date: 2026-11-01
box-skill: deferred to #140
---

**Breaking:** Release approval is the owner's per-PR merge-ok at the CHANGELOG cut PR's head, checked by the publish job with the RELEASE_OWNER actor check; landing the cut triggers validation, tagging the merge commit, publishing and release-issue notice. Migration: approve each cut PR at its head instead of approving a deployment after dispatch; workflow implementation follows in #387. Dispatch remains for dry runs and owner-only manual fallback; no standing grant or auto-applied default publishes. The release design, release-approval registry row and workflow usage docs agree (#274).
