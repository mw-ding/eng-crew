---
type: fixed
issue: 1347
pr: 1608
date: 2026-11-10
box-skill: none
---

`mdstack migrate` accepts a team reference `<file>#<repo>` for `--project` and `--to`: it previously opened the reference as a literal path (`FileNotFoundError`) and used the team file's directory as the git checkout. It now splits the reference, rewrites the team file itself, checks the repo section's declared `checkout`, so a team file outside every clone relocates, and leaves a sibling repo's state folder and `[repos.<name>]` section untouched. Operational records keep the `#<repo>` suffix, and the printed next steps name the new reference. The live-session, land-lock and existing-destination refusals are unchanged.
