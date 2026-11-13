---
type: added
issue: 1774
pr: 1833
date: 2026-11-13
box-skill: none
---

Owner-confirmed `mdstack grant prune` and interactive `mdstack down` archive finished finite grant clauses before a grant-only profile edit, preserving standing permission, restrictions, unknown scope and existing shutdown safeguards. Dry-run previews and `down --keep-grant` provide inspection and opt-out; role, noninteractive and preserve shutdowns skip pruning.
