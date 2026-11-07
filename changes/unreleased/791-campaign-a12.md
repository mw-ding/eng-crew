---
type: added
issue: 791
pr: 1080
date: 2026-11-06
box-skill: none (internal campaign fixtures, test and doc; no template or box-skill changes)
---

The M25 campaign gains the A12 (typed and inline evidence) scenario spec in `scripts/fixtures/campaign/` (25.09), with a sample CLI, service and API and a validator reproduction helper in `A12-sample/`. It runs at level a. CLI create→complete→delete, service, API and web-view captures reproduce exit, stdout and stderr in a fresh clone at the PR head. A failed command's capture keeps its own exit line, so the helper's exit 0 never reads as a pass. A stale capture or a changed head is refused, and a recapture at head agrees. `crew train check` blocks missing artifact-shaped paths, ignores prose, template and scratch paths and counts builder-signed fix proof only at head. Its last step expects a user-attachments screenshot, and a missing-artifact citation repaired by signed proof at head, to read `manual` (fixed by #1078 and #1079). The mobile gap is stated explicitly.
