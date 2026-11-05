---
type: added
issue: 914
pr: 1040
date: 2026-11-05
box-skill: none (no Grok Bot template or render changes)
---

Profiles now accept `runtime.name = "session"` for a hosted or hand-started
coordinator session whose workers run as native subagents or external
harness CLI runs. Its options are `max_active_milestones`, `session_backend`
(`native` or `cli`), the `builders` and `reviewers` pool limits, and the tmux
land-policy options the synthesizer brief renders. `crew-render` writes the
full session brief set: the coordinator and new builder, reviewer and
synthesizer briefs, each one pass per run and ending where the coordinator
appends the `crew brief` run block. A new `<control-item:set>` /
`<control-item:none>` template block renders only with or without
`repo.control_item` (a tracker-native item counts), so a profile with no
control item gets a coordinator brief without inert ownership and handoff
text. The example profile is `profiles/session.toml`. tmux and Grok Bot
profiles validate, resolve and render as before.
