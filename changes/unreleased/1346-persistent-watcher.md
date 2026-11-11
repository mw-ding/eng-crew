---
type: fixed
issue: 1346
pr: 1620
date: 2026-11-10
box-skill: none
---

The tmux watcher no longer depends on a coordinator turn ending cleanly. `mdstack up` (and `mdstack upgrade`, after its reload) now starts a persistent, token-free watcher in its own session (`mdstack watch --persistent --detach`, output in `wake/watcher.log`). It nudges the coordinator and keeps scanning instead of exiting, and nudges again while `wake/queue.jsonl` stays undrained, so polling, routing and ask-deadline wakes continue after a model-gateway error without an owner re-arm; a fatal API error over the coordinator's idle composer still gets the wake line, which only a real approval prompt withholds. One watcher runs per state dir: it holds `wake/watcher.lock` for its whole life, code-change re-execs included, so a second or simultaneous start exits 0 naming the armed PID; PID-file cleanup stays PID-checked. `mdstack guard` names a live watcher whose PID file is missing instead of blocking, and `mdstack down` and `mdstack upgrade` stop the watcher first (found through the lock when its PID file is lost; an unidentified holder is refused, never signalled), `down` even with no session left. `CREW_WATCHER=off` keeps the coordinator-armed one-shot watcher (#399).
