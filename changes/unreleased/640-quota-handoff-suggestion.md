---
type: added
issue: 640
pr: TBD
date: 2026-11-03
box-skill: none (docs and the tmux and session coordinator briefs; no Grok Bot template change)
---

The coordinator gains a quota handoff suggestion duty (build issue D in `docs/handoff.md`): at each wake the owning coordinator checks its own runtime's orchestration meter against the quota routing skip thresholds (15% of the short window, 10% of the weekly or monthly limit) and, under one, suggests a handoff to the owner once per meter window with the meter, reset time, target runtime and the work that would move. The suggestion is not an owner ask (no deadline, no default; silence means no handoff) and only the owner's `/crew handoff to` starts one. Grok Bot exposes no meter, so there it runs only on an owner-given reading. The tmux and session coordinator briefs point at the duty.
