---
type: added
issue: 879
pr: TBD
date: 2026-11-04
box-skill: none (reference docs only; no rendered template change)
---

Design note for deterministic content rules in the sensitive class, marked
proposed and not yet in force. `docs/profile.md` sets out optional
`[[sensitive.content]]` entries (name, regex pattern, optional path scope,
reason), the `sensitive --diff` input made without rename folding, exit 3
for missing or incomplete diff input, and the JSON output that #880's
bindable classifier shares: `label` and `matches` are unchanged and
`content` lists rule, path, side and line. `docs/interfaces.md` proposes an
optional `change.read-diff` operation, needed only when content rules exist.
`docs/protocol.md` records the override scope: an owner override covers
recorded rule and path matches, and a new pair needs reconsideration.
Classification is unchanged until the implementation slices land.
