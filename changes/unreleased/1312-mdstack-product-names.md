---
type: changed
issue: 1312
pr: 1315
date: 2026-11-07
box-skill: deferred to #140
---

**Breaking:** 7.0.0 is a fresh install: reinstall from scratch (docs/guides/migration.md); no 6.x or older install is carried forward. The product is now named mdstack, after the repo moved to `github.com/mw-ding/mdstack`: the release bundle is `mdstack-<version>.tar.gz` with top directory `mdstack-<version>/` (its `SHA256SUMS` entry follows), the host toolkit is `toolkit/mdstack-<version>/`, the install link is `<state>/mdstack`, the profile key is `paths.mdstack` and the pack pin is `pack.mdstack_version`, and docs, templates and the README use the new name and repo URL. The old names are not accepted (no alias for `paths.eng_crew` or `pack.eng_crew_version`, no `<state>/eng-crew` link, no `eng-crew-<version>` bundle or toolkit lookup), and the pre-7.0 compatibility layer is removed: the `crew` CLI shim (`cli/crew`), the 6.0.0 old-path shims under `scripts/` (`scripts/crew`, `scripts/crew-*.py`, `scripts/crew.d/`, `scripts/session.d/`, `scripts/harness.d/`) with old-directory adapter discovery, the `packs/github/manifest.toml` copy, the old `crew` turn-end guard and start-wrapper recognition, and `test-compat-shims.py`. `crew:` labels, markers, `CREW_*` variables, issue links and historical records keep their names.
