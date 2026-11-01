---
type: fixed
issue: 289
pr: 313
date: 2026-10-31
box-skill: none
---

tmux stuck detection (patch): a role window sitting on a Codex command
approval prompt, the Codex `Trust this folder?` screen, a Claude Code
permission prompt (`Do you want to proceed?`, `Do you want to make this
edit to …?`) or idle after a fatal API error (`"type":"error"` with a 4xx
or 5xx status) probed `alive`, so `crew status` showed it healthy and
`crew watch` sent no `dialog` wake. `dialog()` in
`scripts/crew.d/_shared.py` now matches each prompt by its heading on a
line of its own plus its footer as the last screen line, and the error by
the harness's own error line (`■` in Codex, `⎿  API Error:` in Claude
Code), so text quoted in a prompt echo or diff does not match. Such a
window probes `ambiguous` and the watcher wakes the coordinator with
`dialog` on its next scan. `scripts/fixtures/dialog/` holds captured
screens of each case plus working screens that quote the same text;
`scripts/test-crew-status.py` and `scripts/test-crew-watch.py` test them.
`docs/runtimes/tmux.md`, `docs/runtimes/harness-adapters.md` and
`scripts/README.md` describe it. Part of #110; refs #262.
