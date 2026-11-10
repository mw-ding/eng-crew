---
type: added
issue: 1032
pr: 1607
date: 2026-11-10
box-skill: none
---

A `pack.harness` file entry can now set `root = "home"` to install its target under the agent home of the user running `mdstack bootstrap` (`$HOME`), for packs whose agents read instructions from a per-user home. The target stays relative and normalized (absolute and `~` targets are still refused) and gets the same refusals, target hash, `drift:` report and uninstall removal as a project target, with no `.git/info/exclude` line; the plan names each home write. Packs without home entries are unchanged.
