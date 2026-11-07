---
type: added
issue: 1247
pr: 1285
date: 2026-11-07
box-skill: none
---

Role routines: each role package gets a `routines/` folder of recurring jobs, `routines/<routine>.toml` with a schedule (an interval with jitter and a profile key, or cron in the owner's timezone), the skill it runs, generic actions, inputs, outputs, a deadline and a miss policy (`skip`, `catch-up-once`, `escalate`). `core/crew-routines.py` validates them and decides when one is due; check-repo's new `routines` check holds them to the actions contract. The researcher's triage sweep, milestone-close sweep and docs pass and the coordinator's backstop (`stale-sweep`) now take their cadence from routine files with unchanged behaviour; metrics refresh and decision-log status are declared but stay manual (`enabled = false`). A lifecycle role whose `wake` lists `routine` is started by a due routine and stays at zero with none due. Seat packages get an empty `routines/`. Adds the `dev.eng-crew.milestone.closed` event type. See `docs/routines.md`.
