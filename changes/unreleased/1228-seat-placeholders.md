---
type: added
issue: 1228
pr: 1268
date: 2026-11-07
box-skill: none
---

Seat placeholders: `roles/seats/{ceo,cto,cpo,coo,cdo,cfo}/` each hold an empty role package (`role.toml`, `SKILL.md`, `skills/`) for content authored elsewhere, and `roles/seats/TEMPLATE.md` documents what to fill in. No personal data; the role registry still reads `roles/eng/` only.
