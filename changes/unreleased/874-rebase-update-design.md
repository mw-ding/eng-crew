---
type: added
issue: 874
pr: 960
date: 2026-11-04
box-skill: deferred to #140
---

Design note for a rebase update from base in `docs/interfaces.md`, not yet
active: an optional pack-manifest `[strategy]` table
(`update_from_base = "merge" | "rebase"`, default `merge`, so unchanged
manifests stay valid) and `retains_prior_heads`, which `rebase` requires. It
states the replacement guarantee (every earlier head stays readable on the
review backend, stacked children restack with their parent), keeps verdict
portability and the `pass=merge-up` marker unchanged, renders the update
wording from the declared strategy with GitHub renders byte-identical, and
refuses `crew train build` and `crew train bisect` on a rebase backend. It
follows owner decision 3 on #649. The protocol, `docs/packs.md` and the tmux
train section point to it. Build slices B1 to B3 (#951 to #953) follow.
