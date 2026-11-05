---
type: added
issue: 961
pr: 981
date: 2026-11-04
box-skill: none (scripts and reference docs; no rendered template change)
---

Profiles and pack manifests accept an optional `classify` concern with one
operation, `sensitive` (#880 slice B1): a pack binds its sensitivity
extension with `[backends.classify]`, `[capabilities.classify] sensitive =
"supported"` and a `[classify] sensitive` command in its backend map.
`emulated` is refused. `crew-config.py resolve` refuses a binding whose
effective capability is not `supported`, whose backend map has no command
or whose command holds an unfilled placeholder, and prints the bound
command as `classify.sensitive` pack metadata. Undeclared means the
built-in classifier alone, so every existing profile and manifest, the
bundled `github` pack, bootstrap and the default render are unchanged.
Nothing runs the extension until slice B2.
