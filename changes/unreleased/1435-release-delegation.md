---
type: added
issue: 1435
pr: TBD
date: 2026-11-09
box-skill: deferred to #140 (profile mirror_deferral)
---

A recorded standing release delegation: the owner can set `runtime.options.release_delegation` once to their recorded words with a `https://` link, instead of replying in chat for every cut. While it is set, the coordinator's head-pinned merge-ok on a release cut PR (`cmd-id=release-delegation`), citing the delegation, satisfies the synthesizer's §7 cut check and `release.approve-check`. The default `none` keeps today's per-cut owner merge-ok. A pack cannot set the key, and a set value must carry a link. The `RELEASE_OWNER` actor check, CI, release validation, holds and `crew:sensitive` are unchanged; a sensitive cut still needs the owner's own words. `docs/release.md`, the release gate registry row, the runtime options table and the tmux coordinator and synthesizer briefs describe it.
