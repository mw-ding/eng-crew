---
type: added
issue: 1440
pr: 1478
date: 2026-11-08
box-skill: none
---

Campaign scenario A28 gains a two-full-team preflight and lifecycle for the handoff round trip (#213). `campaign-sandbox.py setup --teams 2` builds a second team in the sandbox. It gets its own clone of the one origin, its own session and roots, and an `--org-profile` file that sets its `runtime.instance` and the one control item. `--engine ENGINE/MODEL` leaves that engine unstubbed for both teams. `teardown` refuses when a team's profile changed since setup or resolves a root outside the sandbox or on a production root. Otherwise it runs `mdstack down --preserve` for every team before it kills that team's session. `dev/tests/scripts/fixtures/campaign/a28/teams.py` first tears down every earlier run under its root through that run's manifest, never with a bare tmux call (#1474), and refuses a run without a valid manifest. It then checks the preflight: separate roots, sessions and runtime instances, and the same repo, control item, source, release and skills. It then starts both full teams with `mdstack up` and waits until the coordinator and each enabled lead probe alive. It tears down with both teams stopped, each team's unlanded commit retained and the sentinel unchanged.
