---
type: added
issue: 1523
pr: TBD
date: 2026-11-09
box-skill: none
---

Reflection reports now reach the owner and become build work through the coordinator (#1403 R7). A new coordinator `protocol-reflection` skill relays one digest per report, only its top three proposals with links and recommended defaults, and an unanswered digest changes nothing. Each accept, reject or correction is recorded explicitly in a `reflection-decision` comment on the reflection log issue, which the researcher's cooldown now reads. An accepted proposal becomes one normal issue per independent deliverable, reusing an open issue that covers it, with acceptance criteria, exact paths, the source proposal and an effect measure; protocol, template, gate, spec and profile-default changes are marked for the owner's per-change merge-ok. Memory, profile and pack findings route to their owners. `docs/self-improve.md` gains a Coordinator handoff subsection and the tmux coordinator brief points to the skill.
