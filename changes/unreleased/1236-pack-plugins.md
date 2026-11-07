---
type: added
issue: 1236
pr: TBD
date: 2026-11-07
box-skill: none
---

Packs can now bring their own code. A pack directory with a `pack.toml` declares the eng-crew release versions it supports (`framework`, such as `">=5.3.0, <6.0.0"`) and what it provides: connectors, harness adapters, environment defaults and skills. The new loader, `core/crew-pack.py`, checks each item with the loader its built-in kind already uses. Resolve then layers the pack as core, default profile, pack, project: a pack connector is selectable by `backends.<concern>.name`, a pack harness by engine name (and `crew spawn` launches it), and environment defaults apply when the runtime matches. A pack never replaces a built-in name. Bootstrap and upgrade refuse a pack whose range excludes the installed release tag, or whose checkout is not clean. `install.json` records the pack's name, version, framework range and git commit. The loader refuses a pack that loosens a core floor: a floor control, a merge grant, or a flavor less strict than `standard`. `crew pack list --project <file>` lists built-in and pack items. `crew pack test <dir>` runs the new actions/ conformance kit (`actions/contract.py`) against a pack's connector action binding and harness adapters with fakes, for the pack's own CI. Packs without `pack.toml` work as before.
