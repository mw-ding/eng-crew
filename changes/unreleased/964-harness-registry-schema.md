---
type: added
issue: 964
pr: 978
date: 2026-11-04
box-skill: none (scripts and reference docs; no rendered template change)
---

Pack manifests accept an optional `pack.harness` naming a harness pointer
registry file (slice B1 of #883). `crew-config.py validate` and `resolve`
check it statically: the registry and every `source` and `launch_note`
resolve, symlinks followed, to a regular UTF-8 file inside the pack;
`[[pointer]]` entries take the file or Codex launch-note keys only, name an
adapter bootstrap installs for (`claude-code` or `codex`), use mode `copy`
or `pointer`, and give a unique, normalized project-relative target that is
not a built-in bootstrap target. Bootstrap does not install the entries yet
(#965, #966). Manifests without `pack.harness` validate as before.
