---
type: fixed
issue: 1350
pr: TBD
date: 2026-11-10
box-skill: none
---

`crew-config.py resolve` prints `pack.version = "<version>"  # pack:<name>` for a wired `pack.toml` pack again, read from its `[pack] version`, so a pack that moved from a config-only manifest to the plug-in tree keeps its release identity in the resolution output. An external manifest's version still takes precedence and prints as before; a pack with no version prints nothing.
