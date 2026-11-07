---
type: changed
issue: 1221
pr: 1253
date: 2026-11-07
box-skill: none (every rendered brief is byte-identical)
---

Every eng role's shared policy now has one source in the Agent Skills format. Each role directory under `templates/policy/` (builder, reviewer, synthesizer, coordinator, researcher) has an entry `SKILL.md`, and each procedure has a `skills/<skill>/SKILL.md`. Each skill file has `name` and `description` front matter and names the fragments it is made of. Skill files never render. More repeated policy moved into fragments: the flavor header (8 builder, reviewer and Grok Bot synthesizer templates), the builder signing rule, the local-tools rule, the Grok Bot coordinator signing rule, the landing-authority-and-steering paragraph (coordinators and synthesizers) and coordinator milestone admission. A new parity test checks the skill front matter, links and fragment coverage. Every rendered brief for the default, tmux, session, parity-fixture and eng-crew profiles is byte-identical to before.
