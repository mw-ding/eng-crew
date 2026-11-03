---
type: added
issue: 606
pr: 688
date: 2026-11-03
box-skill: none
---

Add `[runtime.options.launch]` to the tmux profile: `coordinator` (`tmux` or `none`, a preflight-only `crew up`), `roles` (`tmux`, `hosted` or `none`; `crew up --coordinator-only` for one run), `resume` (`fresh`, `ask` or a Claude Code or Codex session id) and `reconcile` (`backend`). With the table absent `crew up` is unchanged; with hosted or no roles it opens only the coordinator window, tagged as before, and starts no lead windows. The control-item ownership read now follows `backends.markers.name`: for a non-GitHub backend, `crew up` records its rendered `markers.read-item` command and the read runs it instead of `gh api`, failing closed to read-only. The tmux runtime doc lists each reconciliation read by backend operation, with a placeholder non-GitHub pack binding.
