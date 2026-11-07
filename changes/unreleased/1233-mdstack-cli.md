---
type: changed
issue: 1233
pr: 1301
date: 2026-11-07
box-skill: none
---

The CLI is renamed `crew` → `mdstack`: `cli/mdstack` is the entry point, `$CREW_BIN` and the Claude Code turn-end guard hook now name it, and the docs, templates, briefs, command usage lines and tests say `mdstack <command>`. `cli/crew` stays for one release as a shim that prints a deprecation note on stderr and then runs `cli/mdstack` unchanged; `scripts/crew` still runs it. A guard hook that names the old `crew` path is recognised and re-pointed at `mdstack` by `mdstack up` and `mdstack migrate`. Anchors to the `docs/runtimes/tmux.md` command sections are now `#mdstack-<command>`. Environment variables (`CREW_*`), the `crew.d/` module directory, `crew.toml`, state paths and `crew:` labels and markers keep their names.
