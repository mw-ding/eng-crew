---
type: fixed
issue: 1480
pr: 1650
date: 2026-11-10
box-skill: none
---

The tmux adapter's `new_session()` now confirms the session exists after `tmux new-session` returns and raises otherwise. tmux can print `error creating …` and still exit 0, which left the remote runner beating with no session and `version` reporting `runner: down` indefinitely. The runner now stops with that error instead of writing `runner.json`. #1487's creation of the default socket directory (mode 0700) is unchanged.
