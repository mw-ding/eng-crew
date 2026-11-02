---
type: added
issue: 337
pr: 428
date: 2026-11-01
box-skill: none
---

Bootstrap can fetch a release with `--version`, verify its SHA256SUMS before extraction, and run it from a separate version directory. Existing bundles and live installs remain protected, rc tags require `--pre`, and an org pack must pin the stable installed tag. The install record retains the verified bundle checksum. Fetching preserves post-apply self-tests and the opt-in smoke request.
