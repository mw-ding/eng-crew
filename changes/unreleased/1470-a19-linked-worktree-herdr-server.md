---
type: fixed
issue: 1470
pr: 1681
date: 2026-11-11
box-skill: none
---

The A19 smoke runs each binding in a detached linked worktree of its source checkout, as `mdstack spawn` does, and removes only that worktree after the run stops; an unmet Claude Code role trust check for the source's repository root blocks the binding instead of stopping at the folder-trust dialog (#1470). `mdstack doctor` gains a `session server` row for herdr: runs inherit the shared server's environment and sandbox, so a server whose holders read sandboxed (macOS `sandbox_check`) fails, with unknown provenance a warning and a stopped server a human step; mdstack still never starts or stops that server (#1469).
