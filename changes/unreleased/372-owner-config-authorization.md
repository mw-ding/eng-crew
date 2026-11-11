---
type: changed
issue: 372
pr: 1708
date: 2026-11-11
box-skill: none
---

Coordinator briefs now carry an owner-config rule (in full for session and the Grok Bot routines; the tmux brief points to it to fit its size budget): before editing the owner's profile, team file or config, the coordinator reads the recorded owner authorization and its scope. A covered edit is applied and reported with its key and authorizing record, with no new ask; a documented repair stays within its stated authority; an uncovered edit or unusable path keeps the owner's config, is reported with the reason and goes to the §6 owner-decision path. Owner-only settings keep their restrictions. `docs/roles.md` gains the matching coordinator section.
