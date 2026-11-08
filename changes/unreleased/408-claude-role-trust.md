---
type: fixed
issue: 408
pr: TBD
date: 2026-11-08
box-skill: none
---

`mdstack doctor` now checks Claude Code folder trust for the checkout role worktrees come from, as a `claude role trust` row. Claude Code keys a linked worktree's trust on its repository root, so with `paths.checkout` outside the profile's directory (the `~/.mdstack/` layout) the coordinator's trust answer no longer covered role windows, and every Claude Code builder or reviewer on a fresh clone stopped at the trust dialog. Until the checkout is trusted the row is a human step: run `claude` once in the checkout and pick `Yes, I trust this folder`. mdstack never writes the Claude Code config; there is no supported per-process pre-trust flag. The tmux onboarding runbook lists the step as a prerequisite and the Claude Code adapter docs describe it.
