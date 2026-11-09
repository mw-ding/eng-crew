---
type: added
issue: 1053
pr: TBD
date: 2026-11-09
box-skill: none
---

The `session` runtime now accepts `runtime.options.present_builders` and `present_reviewers`, the owner-present admission limits that were tmux-only. They default to the full `builders` and `reviewers` caps, a value above the full cap is refused, and the session coordinator brief renders them. tmux behaviour is unchanged.
