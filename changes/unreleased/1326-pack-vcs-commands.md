---
type: added
issue: 1326
pr: 1503
date: 2026-11-09
box-skill: none
---

A `pack.toml` pack whose directory is not a git checkout, such as a subdirectory of a monorepo served by another version control tool, can now pass the install pin: an optional `[vcs]` table declares a `clean` command (exits 0 and prints nothing when the working copy is clean) and a `commit` command (prints the commit), which bootstrap and upgrade run in the pack directory instead of `git`. A failing command, an empty commit or any `clean` output still refuses the pack, and the loader checks the table's shape. Packs without `[vcs]` keep the git checks.
