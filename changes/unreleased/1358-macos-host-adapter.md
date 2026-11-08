---
type: added
issue: 1358
pr: 1410
date: 2026-11-08
box-skill: none
---

The host entrypoint now picks a host OS adapter from `hosts.<name>.capabilities.os`, checked against its own uname: `mdstack host check` gains a `capabilities` row that fails on a mismatch (check 5), and `mdstack host prepare` fails step `capabilities` before changing anything. The first adapter is `macos`: a launchd agent with `KeepAlive` in the account's `gui/<uid>` domain (install, start, stop, status, uninstall), Darwin `ps` start times, and a read-only SSH listener row that warns on a wildcard or public address on the port the client resolves. The runner row also shows the launchd state next to the heartbeat. Proof uses fakes only; real launchd proof waits for the macOS VM or the owner's host. The `linux` adapter is lab item E.
