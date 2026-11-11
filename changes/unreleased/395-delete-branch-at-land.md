---
type: changed
issue: 395
pr: 1636
date: 2026-11-10
box-skill: none
---

Head branches are now deleted by the land itself, not by a later close-out call that a host may refuse as destructive. A change backend may map the conditional `change.land-delete-arg` operation, the argument that makes a land also delete the head branch; GitHub maps it to `--delete-branch`. With it, the sync tmux and session synthesizer briefs add it to the land only for a same-repository head that is neither the default nor the base branch, and `mdstack train land` adds it to each member's merge under the same check in code. A fork, default, base or unreadable head lands without it. Each train merge record says `Head branch: deleted at merge`, `retained (<reason>)` or `delete failed (<reason>)`, and a non-zero exit after a landed merge is read back as a landed merge with a failed delete. Route's close-out still runs its guarded delete only when the branch is still there after the merge, as a fallback, and names why it kept a branch.
