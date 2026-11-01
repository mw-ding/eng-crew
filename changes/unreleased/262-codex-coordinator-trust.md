---
type: fixed
issue: 262
pr: TBD
date: 2026-11-01
box-skill: none
---

tmux: a Codex coordinator now starts pre-trusted like a role window. `crew up`
still launched it with `-c projects."<project-dir>".trust_level="trusted"`, the
key form that did not stop codex-cli 0.164's `Trust this folder?` dialog, and
with the project path as given rather than its real path (on macOS a temp path
under `/var` is really under `/private/var`). It now gets the same per-process
`projects` table as role windows (#293), from a new `codex_trust()` helper in
`scripts/crew.d/_shared.py` that `harness()` also uses: the real project
directory and, in a git repository, its repository root, where Codex applies a
linked worktree's trust. `~/.codex/config.toml` is still never edited. The
detection half of #262 shipped in #289: a window showing the dialog probes
`ambiguous` and wakes the coordinator. Pre-resolving Codex's `Hooks need review`
gate stays the owner's host-level step; a safe design for it is proposed in
the PR, not built. `scripts/test-crew-up.py` tests both launches;
`docs/runtimes/tmux.md` and `docs/runtimes/harness-adapters.md` show the new
coordinator launch.
