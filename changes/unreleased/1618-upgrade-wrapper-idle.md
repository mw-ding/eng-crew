---
type: fixed
issue: 1618
pr: 1637
date: 2026-11-10
box-skill: none
---

`mdstack upgrade --yes` now applies on a host whose role windows run under a launcher wrapper. Its in-flight wait counted any live child process under a role pane as a running pass, so an idle window whose wrapper keeps the native harness and MCP servers alive read as busy until `--wait-timeout`, and the upgrade exited without writing the install. A live child now counts as idle when the harness adapter's idle screen shows (its composer glyph opening a line, no mid-turn text and no blocking dialog) and the window has no pending or unacknowledged inbox message. A mid-turn screen, a dialog, an unrecognized screen or a failed process probe still counts as busy, and the timeout message now names the reason, for example `in-flight pass ash: live child process and no idle prompt on screen`.
