---
type: changed
issue: 179
pr: 390
date: 2026-11-01
box-skill: none
---

Grok Bot and tmux bindings declare supported harness adapters and session backends against runtime contract v2 (roadmap 15.6). Grok Bot uses platform-managed turns, with no terminal adapter/backend, and explicitly declares its missing handle-plus-start-time identity probe; tmux declares Claude Code, Codex and tmux support, including the uninstalled and unverified Codex coordinator guard. Existing waiting-cost and unlanded-work teardown gaps remain declared. Docs only; no rule, gate or code change.
