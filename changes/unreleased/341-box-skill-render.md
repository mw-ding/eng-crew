---
type: added
issue: 341
pr: 543
date: 2026-11-02
box-skill: deferred to #140
---

Grok Bot renders eng-pr-pipeline and eng-crew-roles skills from the bundle's reviewed docs alongside routines, so deployment and render-vs-live drift checks replace hand mirroring. Budget measurement uses fixed path tokens for included skill links, keeping byte counts independent of the install root.
