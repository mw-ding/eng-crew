---
type: fixed
issue: 1187
pr: TBD
date: 2026-11-07
box-skill: none
---

A tmux synthesizer that stops on a `land` message without posting (the PR is closed or merged, or the event SHA is stale) now appends `done: #<n> <sha> stale` (`done: #<n> stale` when the message named no SHA), and that line completes the acknowledged message, so each fresh synthesizer spawn no longer replays every historical land and re-checks each PR on GitHub before the current land; `crew route` treats the stale `done:` as a terminal synthesizer line, reaping an idle synthesizer instead of waking the coordinator.
