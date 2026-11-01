---
type: fixed
issue: 370
pr: 406
date: 2026-11-01
box-skill: none
---

`crew up` refuses before rendering when a profile can use Codex and a host
`hooks.json` or inline `config.toml` hook lacks stored trust. The read-only
check shares `crew doctor`'s host-hook check, tells the operator to review
hooks once in plain Codex, and never writes config or recomputes trust hashes.
