---
type: added
issue: 204
pr: 358
date: 2026-11-01
box-skill: none
---

Host inventory and project affinity in the profile (20.2): optional
`[hosts.<name>]` tables (primary, capabilities, `max_runs`, roles) and a
`[placement]` table (affinity hosts and capability rules), documented in
`docs/profile.md`. `scripts/crew-config.py validate` names hosts by overlay
network name only (an IP literal, `@` or `:` fails) and rejects an unknown
capability, zero or several primaries, unknown placement hosts, uncovered
roles, unmeetable rule needs and `[hosts]` outside the tmux runtime; the
secret-pattern scan covers every host value. Part of #110.
