---
type: fixed
issue: 1106
pr: TBD
date: 2026-11-06
box-skill: none (campaign runner script, its test and the harness doc; no template or box-skill changes)
---

`campaign-run.py` no longer passes the operator's forge tokens (`GH_TOKEN`, `GITHUB_TOKEN`, `GH_ENTERPRISE_TOKEN`, `GITHUB_ENTERPRISE_TOKEN`) or SSH agent (`SSH_AUTH_SOCK`, `SSH_AGENT_PID`) into sandbox scenario steps, and points `GH_CONFIG_DIR` at `<state>/gh-config`, so a step that calls `gh` by absolute path or `git` over SSH cannot use the owner's live credentials.
