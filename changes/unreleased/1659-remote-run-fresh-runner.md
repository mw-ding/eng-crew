---
type: fixed
issue: 1659
pr: TBD
date: 2026-11-12
box-skill: none
---

The `RemoteRun` spawn tests in `test-crew-spawn.py` no longer depend on setup finishing within the fake host's runner freshness window. Their spawn helper rewrites the runner heartbeat just before each spawn, so a loaded host whose setup takes longer than 3 × interval no longer gets a `runner down` refusal. Every spawn assertion now prints the spawn's stdout and stderr, so a future failure shows why. A new case ages the heartbeat past the window: an unrefreshed spawn is still refused with `runner down`, then the refreshed spawn starts the run. Production freshness (`crew-remote.py`) is unchanged, and this does not prove the original failure's cause.
