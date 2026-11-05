---
type: added
issue: 965
pr: TBD
date: 2026-11-05
box-skill: none (scripts and reference docs; no rendered template change)
---

`crew bootstrap --harness` installs a pack's `pack.harness` registry
entries for the selected harnesses (slices B2 and B3 of #883): `copy`
writes the source bytes, `pointer` writes one `Read <source> and follow
it.` line, and a Codex `launch_note` extends the printed launch prompt.
Every registry target gets the built-in refusals (tracked, symlinked,
edited or unowned, all listed before any write), an anchored exclude line
and a target hash; `install.json` gains `harness_pointers` only when a
registry target installs. `crew upgrade` re-plans on a changed registry or
source even with an unchanged render and tag, rewrites unchanged targets,
reports edited ones as `drift:` without writing, and removes unchanged
targets of dropped entries. Uninstall now also removes the anchored exclude
lines bootstrap writes. Without a registry, output and `install.json` are
unchanged.
