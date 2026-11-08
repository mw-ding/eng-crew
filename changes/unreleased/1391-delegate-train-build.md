---
type: changed
issue: 1391
pr: 1401
date: 2026-11-08
box-skill: deferred (profile mirror_deferral)
---

On tmux a builder now builds every merge train, so the synthesizer keeps surveying, gating and landing other ready PRs while a train assembles, waits for CI or bisects. `mdstack train delegate <pr>...` reserves the next train number in `trains/delegated-<n>.json` (base, member heads, synthesizer window) and hands the builder lead a refs-only `train` handoff; the lead starts a train worker with `mdstack spawn builder --train <n>`, which runs `mdstack train build --train <n>` on exactly the recorded base and heads, bisects a red train with `train bisect`, and reports the record to the synthesizer. A base that moved because of a land made meanwhile closes the train unbuilt, and a member whose head moved drops as `head-moved`. A train worker that fails twice ends with `train close <n>`, which now also closes a delegation that has no record yet. Only the synthesizer lands, and every §7 gate, including tested-with-default-branch at `train land`, is unchanged.
