---
type: changed
issue: 1312
pr: 1315
date: 2026-11-07
box-skill: deferred to #140
---

**Breaking:** the product is now named mdstack, after the repo moved to `github.com/mw-ding/mdstack`. The release bundle is `mdstack-<version>.tar.gz` with top directory `mdstack-<version>/` (its `SHA256SUMS` entry follows), the host toolkit is `toolkit/mdstack-<version>/`, the install link is `<state>/mdstack`, the profile key is `paths.mdstack` and the pack pin is `pack.mdstack_version`; docs, templates and the README use the new name and point at the new repo URL. For one release the old names keep working: `paths.eng_crew` and `pack.eng_crew_version` are read as aliases (the new key wins when a layer sets both), bootstrap, upgrade and doctor still find a `<state>/eng-crew` link, and a 6.x tag still fetches its `eng-crew-<version>` bundle and toolkit. Doctor prints a `deprecated` warning for each old name in use, and the new `mdstack migrate --product-names` moves an install's link, profile key and state references to the new names. `crew:` labels, markers, `CREW_*` variables, issue links and historical records keep their names.
