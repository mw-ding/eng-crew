---
type: added
issue: 194
pr: TBD
date: 2026-11-01
box-skill: none
---

Bootstrap self-test enforces per-role UTF-8 byte budgets for rendered briefs
and role-owned runtime Markdown files. The optional `size_budget` profile
table defaults each role to 16 KiB per file; oversized files fail installation
verification with their rendered path, byte count, role and limit.
