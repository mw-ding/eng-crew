---
type: fixed
issue: 1287
pr: 1365
date: 2026-11-08
box-skill: none
---

A team file's `[repos.<name>]` section now takes `checkout`, that repo's `paths.checkout` (absolute, or relative to the team file's directory or to `paths.root` when set). `mdstack spawn` and `mdstack train` found every repo's clone from the team file's directory, so with a team file outside a clone every builder and reviewer spawn failed with `git rev-parse failed: fatal: not a git repository`. Without the key, resolution is unchanged.
