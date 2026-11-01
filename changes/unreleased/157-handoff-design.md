---
type: added
issue: 157
pr: TBD
date: 2026-11-01
box-skill: none
---

Runtime handoff (design): `docs/handoff.md` proposes how the owner pauses one crew runtime on a repo and resumes the same work in another, both ways (for example Grok Bot to a Claude Code or Codex session when orchestration quota runs short). One runtime instance owns a repo at a time, recorded by `pass=handoff` markers on a control item; every other runtime runs read-only. It covers drain, stop and takeover modes, a references-only handoff manifest with its template, an `acked` marker keyed by a handoff id so a retry is never a second handoff, reconcile against live state in dependency-closed sets, prompt stop of the outgoing runtime's wake sources, the return path, session rules as profile and flavor settings, and the build issues (#210 to #213 plus proposed follow-ups). The runtime contract gains C9 Ownership handoff, which the Grok Bot and tmux bindings declare unsupported today, compensated by the manual pause. Roadmap 21.1; part of #110.
