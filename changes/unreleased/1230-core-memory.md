---
type: added
issue: 1230
pr: TBD
date: 2026-11-07
box-skill: none
---

Core memory layer: an owner profile (`memory/owner.md`) and one core memory file per role (`memory/roles/<role>.md`), curated in git with size limits (3000 and 2000 bytes). The renderer appends them to every role's rendered brief, so terminal, session and Grok Bot roles start with them; a lint problem fails the render closed. `core/crew-memory.py` (and check-repo's new `memory` check) refuses personal data and routes it to the knowledge connector. The coordinator's new memory-capture skill proposes promotions from platform scratch as a memory PR. See `docs/memory.md`.
