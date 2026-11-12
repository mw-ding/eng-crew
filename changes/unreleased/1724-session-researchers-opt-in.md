---
type: changed
issue: 1724
pr: 1759
date: 2026-11-12
box-skill: none
---

**Breaking:** on the session runtime the researcher triage sweep is now opt-in: an unset `runtime.options.researchers` defaults to `0`, so `crew-render` writes the four ordinary session briefs (coordinator, builder, reviewer, synthesizer) with the same bytes as before and no `runtime/researcher.md`, restoring the shape a profile without the key had before the sweep brief arrived (#1404). A positive cap writes the sweep brief as before. `triage.enabled = true` with an unset or zero cap is refused, as `0` already was. The session options table now gives the default as `0`, and the session guide and sample profile say the same. Tmux keeps its default of 2. Migration: a session profile that runs the triage sweep, including one with `triage.enabled = true` that relied on an omitted cap, sets `runtime.options.researchers` to a positive value, for example `researchers = 1`; a profile without the sweep needs no edit.
