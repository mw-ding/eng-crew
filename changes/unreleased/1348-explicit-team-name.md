---
type: added
issue: 1348
pr: TBD
date: 2026-11-10
box-skill: none
---

A team file can set `[team] name = "<team>"` (`[a-z0-9-]`, 1–63 characters) as its stable identity: it keys the team's state root and `crew-team-<team>` tmux session, so a conventional `~/.mdstack/config.toml`, a renamed file or a symlink to the file resolve the same team, and the file name no longer has to follow the team-name rule. A file without `team.name` keeps its file-name identity unchanged. Changing the name moves the state root and session, so stop the crew and move the state with `mdstack migrate` first.
