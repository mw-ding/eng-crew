---
type: changed
issue: 293
pr: 311
date: 2026-10-31
box-skill: none
---

tmux role-window launch policy (behaviour change: role windows no longer
stop on permission or approval prompts): new profile key
`runtime.options.permission_mode`, `bypass` | `auto` | `safe`, default
`bypass` (firstmate's default, owner decision on #110). `harness()` in
`scripts/crew.d/_shared.py` gives Claude Code `--add-dir
<state-dir>/<owner>__<repo>` in every mode, then `--permission-mode
bypassPermissions --settings '{"skipDangerousModePermissionPrompt":true}'`
(per process; the user's settings are never edited), `auto`, or
`acceptEdits` (`safe`, the old launch). Codex gets
`--dangerously-bypass-approvals-and-sandbox`, or `workspace-write` with
network on (plus `-a on-request` for `auto`), always with `--add-dir
<state>`. Codex pre-trust is now one `-c projects={...}` table for the
worktree and its repo root: the old `projects."<dir>".trust_level` form did
not stop the trust dialog on codex-cli 0.164. `crew spawn` and `crew
restart` pass the mode, `crew-config.py` validates it, and
`profiles/tmux.toml`, `docs/profile.md`, `docs/runtimes/tmux.md`,
`docs/runtimes/harness-adapters.md` and the runbook document it, with the
`auto` / `safe` residual gap. Tests: argv per mode and engine and an unknown
mode refused (`test-crew-spawn.py`), the validator (`test-crew-config.py`)
and the restart launch (`test-crew-restart.py`). The coordinator's `crew up`
launch is unchanged.
