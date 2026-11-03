---
type: added
issue: 584
pr: TBD
date: 2026-11-03
box-skill: none
---

Add the researcher, Riley, to the tmux runtime (part 2 of 3 for the researcher role). `roles/eng.toml` registers a `researcher` role with one `research` pass on an issue, windows 40–44 (`riley-<issue>`), a fresh session per request and the `researchers` cap, so `crew spawn researcher --issue N` starts it (at the deep tier by default) or queues it when the cap is full. The default profile routes it on the research row (`[engines.roles] researcher`: Codex `gpt-6.1-sol`, then Claude Code `opus`, then OpenCode DeepSeek). The identity stays optional: `gh_user` resolves to the coordinator's author login, with the name Riley, title Researcher and emoji 🔬. The new `templates/runtimes/tmux/researcher.md` brief covers the read-only scope, citation rules, the direction rule and the signed `[Riley/research]` finding with its `pass=research` marker. A researcher's `done:` (or `failed:`) is terminal: `crew route` closes its window and leaves the wake for the coordinator to relay. The coordinator rule follows in part 3.
