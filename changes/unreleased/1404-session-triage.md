---
type: added
issue: 1404
pr: 1590
date: 2026-11-10
box-skill: none
---

A session crew can run always-on triage. `mdstack poll --triage-only` runs one triage scan on a tmux or session profile. A non-GitHub tracker backend is scanned through its `tracker.list-items` binding (never `gh`), once per id in the new `[triage] trackers` key. `crew-render` writes a session researcher sweep brief that carries the tmux Triage sweep policy, now a shared policy fragment. The session runtime accepts `runtime.options.researchers`. `docs/runtimes/session.md` documents the hosted `triage-sweep` routine trigger: its schedule comes from `triage.interval_hours`, an empty queue skips the run, and the run prompt names the routine file and skill. tmux behaviour is unchanged.
