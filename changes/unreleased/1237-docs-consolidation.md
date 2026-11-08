---
type: changed
issue: 1237
pr: 1309
date: 2026-11-07
box-skill: none
---

The public docs read as one set for the modular structure. Each module (`roles/`, `connectors/`, `environments/` and `environments/terminal/`, `harnesses/`, `core/`, `cli/`, `profiles/`, `packs/`, `dev/`; `actions/` already had one) has a short README with its purpose, contents and how it plugs in, shipped in the bundle. `docs/README.md` replaces its role-by-role list, a copy of `reading-paths.md`, with reading paths for user, operator, pack author and contributor, and adds a module table that says where the not-yet-split `protocols/` and `install/` content lives. `docs/concepts.md` adds the four axes (role, connector, environment, harness) and the team terms (generic action, seat, staff and team head, routine, core memory, module), and maps runtime, backend and profile onto them. `docs/architecture.md` gains a Modules section with a Mermaid diagram of the axes and the layout. `docs/specs/framework.md` marks its bootstrap layout, sources and slices historical while R1–R8 stay cited, and the README's spec link names the team and portable specs too. Four design docs the docs scan flagged gain status banners. No rule, gate, marker or default changes.
