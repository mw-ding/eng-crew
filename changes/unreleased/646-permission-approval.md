---
type: added
issue: 646
pr: 690
date: 2026-11-03
box-skill: deferred to #140 (protocol return-brief line)
---

Add `scripts/crew-permit.py`, an owner-installed Claude Code `PermissionRequest` hook that auto-approves a crew role's prompt only while a bounded, non-quiet away entry is open. The checker is an allowlist of six rule families (read, crew, write, tracker, assign, setup), decided from its own tokenizer's argv; substitution, eval, unknown variables, repo-selector spoofing, symlinked or crew-writable trust files and recursive deletes that touch a root all ask. Each approval sends an FYI first (a tracking-issue comment, or a pack's `fyi` command) and is logged for the new return-brief `Auto-approvals` section. Trust settings live in an owner-only file outside every crew root. Bootstrap lists the install as an optional owner-only step, and `install` refuses inside a crew session. See `docs/permit.md`.
