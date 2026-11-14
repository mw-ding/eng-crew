---
type: added
issue: 1857
pr: 1875
date: 2026-11-13
box-skill: none
---

A team file's repos now share one crew scheduler. `mdstack schedule` keeps one lock, target and reservation ledger under the team root's `schedule/`, so two repos' leads deciding at once never over-admit the last slot. It counts every repo's workers once against the team's pool caps, floors, target and ramp limit. Each repo's demand is filtered by that repo's ownership, pause, holds and `crew:escalated` label, read through its `repo.labels`. An unreadable repo blocks only its own demand, recorded as `blocked`. Unreadable caps, workers or ledger refuse every team decision. Each repo's demand is ranked by its own tracker: milestone order, which honours `repo.milestones`, plus `Depends on` and `main-red`. Ties break by canonical repo and work identity. An acknowledged wait that is still parked is not demand. A decision grants only the caller's `(repo, pool)` lane. A team reservation records its repo, project and reviewer pass kind and round, so the same `#n` in two repos, or one PR's passes and rounds, stay separate grants. It transfers only to that repo's run, and `mdstack spawn` and `mdstack schedule release` drop only the caller repo's grant. Decisions, held items, releases, the decision log, the summary line and the watcher's `schedule-stuck` alarm name the repo. These team outputs are additive. One-repo configs keep their outputs. One change applies to every config: an unreadable `reservations.json` now defers each decision as `reservations-unreadable` and is left as it is, where before it was read as empty and overwritten.
