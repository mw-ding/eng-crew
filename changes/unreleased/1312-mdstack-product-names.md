---
type: changed
issue: 1312
pr: 1315
date: 2026-11-07
box-skill: deferred to #140
---

**Breaking:** the product is now named mdstack, after the repo moved to `github.com/mw-ding/mdstack`. The release bundle is `mdstack-<version>.tar.gz` with top directory `mdstack-<version>/` (its `SHA256SUMS` entry follows), the host toolkit is `toolkit/mdstack-<version>/`, the install link is `<state>/mdstack`, the profile key is `paths.mdstack` and the pack pin is `pack.mdstack_version`; docs, templates and the README use the new name and point at the new repo URL. The old names are not accepted: there is no alias for `paths.eng_crew` or `pack.eng_crew_version`, no `<state>/eng-crew` link and no 6.x `eng-crew-<version>` bundle or toolkit lookup, so reinstall from scratch with a 7.0.0 bundle (docs/guides/migration.md, Product names). `crew:` labels, markers, `CREW_*` variables, issue links and historical records keep their names.
