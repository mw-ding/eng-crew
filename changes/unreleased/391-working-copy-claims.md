---
type: added
issue: 391
pr: 1610
date: 2026-11-10
box-skill: none
---

Runs now claim their working copy host-wide, so two crews on one host (one owner's standing and ad-hoc crews, say) can no longer start runs in the same copy. A claim lives in `~/.mdstack/copy-claims/`, shared by every crew and state root on the host, is keyed by the copy's real path (symlink and `..` aliases are one claim) and records host, path, crew, run, item and time. `mdstack spawn` and a role host's `spawn` verb claim each fresh worktree before adding it and refuse another holder's claim before any worktree or window; a refused or failed launch releases its own claim, and `mdstack kill` releases it once the run is removed (kept unlanded work keeps it). New `mdstack copy-claim acquire|release|show` lets a coordinator claim an existing copy before a hand-dispatched run. Only the holder releases a claim; no age or other crew reclaims one.
