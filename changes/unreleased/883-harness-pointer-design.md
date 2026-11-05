---
type: added
issue: 883
pr: 973
date: 2026-11-04
box-skill: none (reference docs only; no rendered doc or template changed)
---

Design note for pack-declared harness pointers in `docs/bootstrap.md`, not
yet active: an optional `pack.harness` registry whose `[[pointer]]` entries
name a harness with an install pointer adapter (`claude-code` or `codex`), a
project-relative target and a pack source written by `copy` or `pointer`, or
a Codex launch note added to the printed launch line. `validate` checks
targets, collisions with the built-in targets and source containment;
bootstrap installs the entries under the existing refusals, exclude lines,
hashes and uninstall, and records an optional `harness_pointers` field;
upgrade re-plans on pack changes, reports drift on edited targets and removes
dropped entries. Without a registry, behaviour and `install.json` stay
byte-identical. `docs/packs.md`, `docs/profile.md` and the harness adapter
install pointer link to it. Implementation slices B1 to B3 (#964 to #966)
follow.
