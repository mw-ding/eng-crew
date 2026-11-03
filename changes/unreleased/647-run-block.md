---
type: added
issue: 647
pr: TBD
date: 2026-11-03
box-skill: pending coordinator mirror
---

`crew brief` prints the `## This run` block (required `Item`, `Pass`, `Base`; optional `Window`, `Round`, `Slot`, `Host`, `Worktree`, `Engine`, `Claim`, `Flavor`, `Comments`) for any runtime or session backend, and exits 2 with no block when a required field is missing. `crew spawn` builds its tmux block with the same helper (output unchanged). The session runtime docs show hosted dispatch with it, and the worker brief rules say a pass does not start without the block.
