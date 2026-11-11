---
type: fixed
issue: 1618
pr: 1637
date: 2026-11-10
box-skill: none
---

`mdstack upgrade --yes` now applies on a host whose role windows run under a launcher wrapper. Its in-flight wait counted any live child process under a role pane as a running pass, so an idle window whose wrapper keeps the native harness and MCP servers alive read as busy until `--wait-timeout`, and the upgrade exited without writing the install. A window whose harness adapter declares a composer glyph (Claude Code, Codex) is now judged by its screen whatever processes live under the pane: it is idle only when a row opens with that glyph, no mid-turn text or blocking dialog shows and no unsubmitted `inbox:` nudge sits on the composer, besides the existing status and inbox checks (now also an unacknowledged inbox message after a run's `done:`). A message whose `mdstack send` nudge was never submitted (exit 4, for example into a dialog) is now recorded in `inbox/<window>.undelivered`, and the upgrade waits on it until the window acks it or the operator clears the file, so a coordinator message stays pending after the dialog clears. Other adapters keep the live-child rule. A mid-turn, dialog, empty or unrecognized screen, or a failed process probe, still counts as busy, and the timeout message names the reason, for example `in-flight pass ash: no idle prompt on screen`.
