---
type: added
issue: 1329
pr: TBD
date: 2026-11-07
box-skill: none
---

The profile takes an optional team name, `identities.team` (`[a-z0-9-]`, 1–63 characters, default empty). When it is set, tmux window 0 is named `<coordinator name>-<team>` (`ash-mdp-m4`); `up`, `send`, `attach`, the builder lead and the merge train resolve that name from the profile, `status`, `guard` and the watcher keep addressing window 0 by index, and `mdstack attach ash` and `mdstack send ash` still reach it. Templates can use a new `<TeamName>` placeholder, empty when unset. With the key unset or empty, rendered briefs and window names are unchanged, and an invalid value fails `validate`.
