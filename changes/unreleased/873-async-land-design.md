---
type: added
issue: 873
pr: 925
date: 2026-11-04
box-skill: none (reference docs only; no rendered doc or template changed)
---

Design note for an asynchronous land in `docs/interfaces.md`, not yet
active: an optional pack-manifest `[land]` table (`mode`, `opens_draft`,
`serializes`, `tests_against_tip`; default `sync`, so unchanged manifests
stay valid), conditional `change.publish` and `change.land-status`
operations, the synthesizer's intent, poll, record and restart loop, and the
gate alternatives for C7 and tested with the default branch. It follows the
owner's #649 decisions: the final gate check before queue admission,
re-verification on a head change, and a never-requested land told apart from
a failed one. GitHub stays `sync`. `docs/concepts.md`, the runtime contract
C7 and the tmux land lock link to it. Implementation slices B1 to B4 follow.
