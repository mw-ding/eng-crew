---
type: changed
issue: 328
pr: 329
date: 2026-11-01
box-skill: none
---

Upgrade note (2.1): tmux role windows now launch with permission prompts
off by default (`runtime.options.permission_mode = "bypass"`, following
firstmate), so agents run any command in their worktree without asking;
set `"auto"` or `"safe"` in `crew.toml` to opt out. Each project needs a
one-time Claude Code folder trust on its first `crew up`: accept the trust
dialog once in the coordinator's window, which also covers the role
worktrees. Codex windows trust the worktree and its repo root
automatically. Details:
[docs/runtimes/tmux.md](https://github.com/mw-ding/eng-crew/blob/main/docs/runtimes/tmux.md#crew-spawn)
and the runbook's
[tmux runtime](https://github.com/mw-ding/eng-crew/blob/main/docs/runbook-new-repo.md#tmux-runtime)
section.
